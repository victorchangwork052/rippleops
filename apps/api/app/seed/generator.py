"""Deterministic demo-dataset generator.

The dataset is designed around the demo narrative (handoff sections 5 and 16),
not generated at random. Filler values come from a fixed-seed RNG so every run
produces byte-identical data. Anchor facts:

* MCU-X100 (NovaChip Technologies) is used by 12 finished goods in 3 families,
  through 1-4 BOM levels, with effective quantities 1-4 per product.
* MCU-X200 costs 18% more; it is approved except for 4 products that need
  re-validation.
* Current margins of the affected products are calibrated so that 3 fall
  below the 20% target with MCU-X200, and 5 in the compound scenario
  (MCU-X200 + copper +12% + TW-US ocean freight +15%).
* Revenue exposure (next 6 months) is ~US$4.2M and MCU-X100 stock covers
  58 days of demand.

Only the *seed values* are calibrated here. All reported numbers are computed
at runtime by the cost / impact / scenario engines.
"""

from __future__ import annotations

import math
import random
from datetime import date

from app.db.schema import (
    AlternatePart,
    BomEdge,
    ChangeEvent,
    Inventory,
    ItemMaster,
    MaterialExposure,
    MaterialPrice,
    ProductDemand,
    ProductPrice,
    ShippingLane,
    Snapshot,
    Supplier,
    SupplierPart,
)
from app.seed.operations import add_operations_data
from app.services.bom import trace_in_memory
from app.services.costing import CostEngine, CostParams
from app.services.demand import horizon_days, horizon_months
from app.services.index import DataIndex

SEED = 20261018
AS_OF = date(2026, 10, 1)
SNAPSHOT_DATE = date(2026, 9, 30)
BOM_EFFECTIVE_FROM = date(2025, 1, 1)
PRICE_EFFECTIVE = date(2026, 9, 1)
DEMAND_MONTHS = 12
HORIZON_MONTHS = 6
MARGIN_TARGET = 0.20

ANCHOR_PART = "MCU-X100"
REPLACEMENT_PART = "MCU-X200"
COMPOUND = CostParams(
    substitutions={ANCHOR_PART: REPLACEMENT_PART},
    material_adjustments={"COPPER": 0.12},
    freight_adjustments={"TW-US-OCEAN": 0.15},
)

TARGET_REVENUE_EXPOSURE = 4_200_000.0
TARGET_COVERAGE_DAYS = 58.5  # floor() -> 58 days

# --------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------

SUPPLIERS = [
    ("SUP-NOVA", "NovaChip Technologies", "Taiwan", "HIGH", "TW-US-OCEAN"),
    ("SUP-ATLAS", "Atlas Electronics", "Taiwan", "LOW", "TW-US-OCEAN"),
    ("SUP-CRES", "Crescent Semiconductor", "Japan", "LOW", "JP-US-OCEAN"),
    ("SUP-SUMM", "Summit Interconnect", "China", "MEDIUM", "CN-US-OCEAN"),
    ("SUP-MERI", "Meridian Metals", "Taiwan", "LOW", "TW-US-OCEAN"),
    ("SUP-BORE", "Boreal Plastics", "Mexico", "LOW", "MX-US-TRUCK"),
    ("SUP-HELI", "Helix Power Systems", "China", "MEDIUM", "CN-US-OCEAN"),
    ("SUP-KEST", "Kestrel Optics", "Japan", "LOW", "JP-US-OCEAN"),
    ("SUP-PACI", "Pacific Components", "Mexico", "LOW", "MX-US-TRUCK"),
    ("SUP-ORIO", "Orion Materials", "United States", "LOW", "US-DOMESTIC"),
    ("SUP-VANT", "Vantage Packaging", "United States", "LOW", "US-DOMESTIC"),
]

LANES = [
    ("TW-US-OCEAN", "Taiwan", "United States", "Ocean", 3.40),
    ("TW-US-AIR", "Taiwan", "United States", "Air", 8.20),
    ("CN-US-OCEAN", "China", "United States", "Ocean", 2.70),
    ("JP-US-OCEAN", "Japan", "United States", "Ocean", 3.10),
    ("MX-US-TRUCK", "Mexico", "United States", "Truck", 1.15),
    ("US-DOMESTIC", "United States", "United States", "Truck", 0.55),
]

MATERIALS = [
    ("COPPER", 9.80),
    ("ALUMINUM", 2.65),
    ("STEEL", 0.92),
    ("RESIN", 2.15),
    ("TIN", 32.50),
]

# (category, supplier, price range, weight range kg, {material: (min kg, max kg)}, [(id, name)])
COMPONENT_CATEGORIES: list[tuple[str, str, tuple[float, float], tuple[float, float], dict, list[tuple[str, str]]]] = [
    ("Memory", "SUP-CRES", (2.2, 7.4), (0.001, 0.003), {}, [
        ("MEM-D4-4G", "DDR4 Memory 4 Gb"), ("MEM-D4-8G", "DDR4 Memory 8 Gb"),
        ("FLS-EM-16G", "eMMC Flash 16 GB"), ("FLS-EM-32G", "eMMC Flash 32 GB"),
        ("EEP-64K", "EEPROM 64 Kb"), ("NOR-128M", "NOR Flash 128 Mb"),
    ]),
    ("Power IC", "SUP-ATLAS", (0.45, 2.4), (0.0005, 0.002), {}, [
        ("PMIC-100", "Power Management IC 100"), ("PMIC-200", "Power Management IC 200"),
        ("LDO-3V3", "LDO Regulator 3.3 V"), ("LDO-1V8", "LDO Regulator 1.8 V"),
        ("BUCK-5A", "Buck Converter 5 A"), ("BUCK-10A", "Buck Converter 10 A"),
        ("SUP-MON", "Supply Monitor"), ("EFUSE-24V", "eFuse 24 V"),
    ]),
    ("Communication IC", "SUP-ATLAS", (0.8, 9.5), (0.001, 0.012), {}, [
        ("PHY-ETH-1G", "Ethernet PHY 1 Gb"), ("PHY-ETH-100M", "Ethernet PHY 100 Mb"),
        ("XCV-RS485", "RS-485 Transceiver"), ("XCV-CAN", "CAN Transceiver"),
        ("WIFI-M2", "Wi-Fi 6 M.2 Module"), ("LTE-CAT4", "LTE Cat-4 Module"),
        ("BLE-5", "Bluetooth LE 5 Module"), ("SWITCH-5P", "5-Port Ethernet Switch IC"),
    ]),
    ("Passive", "SUP-PACI", (0.004, 0.22), (0.0001, 0.004), {"TIN": (0.00001, 0.00005)}, [
        ("CAP-0402-100N", "Capacitor 0402 100 nF"), ("CAP-0402-1U", "Capacitor 0402 1 uF"),
        ("CAP-0603-10U", "Capacitor 0603 10 uF"), ("CAP-1206-47U", "Capacitor 1206 47 uF"),
        ("CAP-EL-470U", "Electrolytic Capacitor 470 uF"), ("CAP-EL-1000U", "Electrolytic Capacitor 1000 uF"),
        ("RES-0402-10K", "Resistor 0402 10 kOhm"), ("RES-0402-1K", "Resistor 0402 1 kOhm"),
        ("RES-0603-0R", "Resistor 0603 0 Ohm"), ("RES-1206-100R", "Resistor 1206 100 Ohm"),
        ("IND-PWR-4U7", "Power Inductor 4.7 uH"), ("IND-PWR-10U", "Power Inductor 10 uH"),
        ("IND-CM-CHOKE", "Common-Mode Choke"), ("FER-0603", "Ferrite Bead 0603"),
        ("DIO-TVS-24V", "TVS Diode 24 V"), ("DIO-SCH-3A", "Schottky Diode 3 A"),
        ("LED-GRN", "Status LED Green"), ("LED-RED", "Status LED Red"),
        ("XTAL-25M", "Crystal 25 MHz"), ("XTAL-32K", "Crystal 32.768 kHz"),
    ]),
    ("Connector", "SUP-SUMM", (0.35, 4.8), (0.004, 0.045), {"COPPER": (0.002, 0.012), "RESIN": (0.002, 0.01)}, [
        ("CON-RJ45-SH", "RJ45 Shielded Jack"), ("CON-RJ45-2X", "Dual RJ45 Jack"),
        ("CON-M12-4P", "M12 Connector 4-Pin"), ("CON-M12-8P", "M12 Connector 8-Pin"),
        ("CON-TB-8P", "Terminal Block 8-Pin"), ("CON-TB-16P", "Terminal Block 16-Pin"),
        ("CON-USB-C", "USB-C Receptacle"), ("CON-DC-JACK", "DC Power Jack"),
        ("CON-SMA", "SMA RF Connector"), ("CON-HDR-40P", "Header 40-Pin"),
        ("CON-FFC-30P", "FFC Connector 30-Pin"), ("CON-DB9", "DB9 Connector"),
        ("CON-SFP-CAGE", "SFP Cage"), ("CON-POE-MAG", "PoE Magnetics Jack"),
        ("CON-SD-SLOT", "microSD Slot"), ("CON-SIM", "Nano-SIM Holder"),
    ]),
    ("Printed Circuit Board", "SUP-ATLAS", (1.8, 9.0), (0.02, 0.12),
     {"COPPER": (0.008, 0.04), "TIN": (0.0004, 0.0012)}, [
        ("PCB-CORE-6L", "Core Module PCB 6-Layer"), ("PCB-MAIN-8L", "Main Board PCB 8-Layer"),
        ("PCB-MAIN-10L", "Main Board PCB 10-Layer"), ("PCB-IO-4L", "I/O Board PCB 4-Layer"),
        ("PCB-IO-6L", "I/O Board PCB 6-Layer"), ("PCB-VIS-10L", "Vision Module PCB 10-Layer"),
        ("PCB-VIS-12L", "Vision Board PCB 12-Layer"), ("PCB-PSU-2L", "Power Supply PCB 2-Layer"),
        ("PCB-PSU-4L", "Power Supply PCB 4-Layer"), ("PCB-COM-6L", "Communication PCB 6-Layer"),
        ("PCB-CAM-4L", "Camera PCB 4-Layer"), ("PCB-CTL-8L", "Control Board PCB 8-Layer"),
    ]),
    ("Enclosure", "SUP-MERI", (2.2, 9.5), (0.35, 0.9), {"ALUMINUM": (0.3, 0.8)}, [
        ("ENC-AL-S-BASE", "Aluminum Enclosure Base S"), ("ENC-AL-S-COVER", "Aluminum Enclosure Cover S"),
        ("ENC-AL-M-BASE", "Aluminum Enclosure Base M"), ("ENC-AL-M-COVER", "Aluminum Enclosure Cover M"),
        ("ENC-AL-L-BASE", "Aluminum Enclosure Base L"), ("ENC-AL-L-COVER", "Aluminum Enclosure Cover L"),
        ("ENC-RUG-BASE", "Rugged Enclosure Base"), ("ENC-RUG-COVER", "Rugged Enclosure Cover"),
        ("ENC-VIS-HOUSING", "Vision Housing"), ("ENC-VIS-WINDOW", "Vision Optical Window"),
    ]),
    ("Plastic Enclosure", "SUP-BORE", (0.6, 2.8), (0.08, 0.3), {"RESIN": (0.06, 0.25)}, [
        ("ENC-PC-S", "Polycarbonate Housing S"), ("ENC-PC-M", "Polycarbonate Housing M"),
        ("ENC-DIN-RAIL-CLIP", "DIN-Rail Clip"), ("ENC-GASKET-KIT", "Enclosure Gasket Kit"),
    ]),
    ("Thermal", "SUP-MERI", (0.6, 4.2), (0.02, 0.16), {"ALUMINUM": (0.02, 0.12)}, [
        ("HS-AL-40", "Aluminum Heatsink 40 mm"), ("HS-AL-60", "Aluminum Heatsink 60 mm"),
        ("HS-CU-30", "Copper Heatsink 30 mm"), ("FAN-40", "Cooling Fan 40 mm"),
        ("FAN-60", "Cooling Fan 60 mm"), ("TIM-PAD", "Thermal Interface Pad"),
        ("HP-CU-6", "Copper Heat Pipe 6 mm"), ("SPREADER-CU", "Copper Heat Spreader"),
    ]),
    ("Power", "SUP-HELI", (0.2, 6.5), (0.005, 0.3), {"COPPER": (0.002, 0.03), "STEEL": (0.0, 0.02)}, [
        ("XFMR-60W", "Transformer 60 W"), ("XFMR-120W", "Transformer 120 W"),
        ("XFMR-POE", "PoE Transformer"), ("BRIDGE-RECT", "Bridge Rectifier"),
        ("MOSFET-100V", "MOSFET 100 V"), ("CAP-BULK-400V", "Bulk Capacitor 400 V"),
        ("FUSE-5A", "Fuse 5 A"), ("RELAY-24V", "Relay 24 V"),
        ("OPTO-ISO", "Optocoupler Isolator"), ("PFC-CTRL", "PFC Controller"),
        ("CMC-PWR", "Power Line Choke"), ("VARISTOR-275V", "Varistor 275 V"),
    ]),
    ("Cable", "SUP-SUMM", (0.3, 3.2), (0.01, 0.18), {"COPPER": (0.006, 0.08), "RESIN": (0.003, 0.03)}, [
        ("CBL-PWR-2C", "Power Cable 2-Core"), ("CBL-PWR-4C", "Power Cable 4-Core"),
        ("CBL-IO-12C", "I/O Cable 12-Core"), ("CBL-FFC-30", "Flat Flex Cable 30-Pin"),
        ("CBL-COAX-RF", "RF Coaxial Cable"), ("CBL-CAM-MIPI", "MIPI Camera Cable"),
        ("CBL-GND-STRAP", "Ground Strap"), ("CBL-ETH-INT", "Internal Ethernet Cable"),
        ("WIRE-18AWG", "Hook-Up Wire 18 AWG"), ("WIRE-22AWG", "Hook-Up Wire 22 AWG"),
    ]),
    ("Optics", "SUP-KEST", (0.8, 9.0), (0.002, 0.03), {}, [
        ("SEN-CMOS-2MP", "CMOS Image Sensor 2 MP"), ("SEN-CMOS-5MP", "CMOS Image Sensor 5 MP"),
        ("LENS-M12-4MM", "M12 Lens 4 mm"), ("LENS-M12-8MM", "M12 Lens 8 mm"),
        ("LENS-HOLDER", "Lens Holder"), ("IR-FILTER", "IR-Cut Filter"),
        ("IR-LED-850", "IR LED 850 nm"), ("LENS-CS-12MM", "CS-Mount Lens 12 mm"),
    ]),
    ("Mechanical", "SUP-ORIO", (0.01, 0.9), (0.001, 0.06), {"STEEL": (0.001, 0.05)}, [
        ("SCR-M3-6", "Screw M3 x 6"), ("SCR-M3-10", "Screw M3 x 10"),
        ("SCR-M4-8", "Screw M4 x 8"), ("STO-M3-10", "Standoff M3 x 10"),
        ("NUT-M3", "Nut M3"), ("WSH-M3", "Washer M3"),
        ("BRKT-DIN", "DIN-Rail Bracket"), ("BRKT-WALL", "Wall-Mount Bracket"),
        ("SPR-GROUND", "Grounding Spring"), ("CLIP-CABLE", "Cable Clip"),
        ("PLATE-MOUNT", "Mounting Plate"), ("PIN-DOWEL", "Dowel Pin"),
    ]),
    ("Packaging", "SUP-VANT", (0.05, 1.6), (0.002, 0.35), {}, [
        ("BOX-S", "Shipping Box S"), ("BOX-M", "Shipping Box M"), ("BOX-L", "Shipping Box L"),
        ("FOAM-S", "Foam Insert S"), ("FOAM-M", "Foam Insert M"),
        ("LBL-RATING", "Rating Label"), ("LBL-SERIAL", "Serial Label"), ("DOC-QSG", "Quick Start Guide"),
    ]),
]

# Fixed list prices for parts that drive the anchor products' cost. Parts not
# listed here get a seeded random price within their category range.
PRICE_OVERRIDES = {
    "MEM-D4-4G": 3.20, "MEM-D4-8G": 5.60, "FLS-EM-16G": 3.40, "FLS-EM-32G": 5.10,
    "PMIC-100": 1.45, "PMIC-200": 2.10, "LDO-3V3": 0.28, "LDO-1V8": 0.26, "BUCK-5A": 0.95, "BUCK-10A": 1.60,
    "PHY-ETH-1G": 2.10, "PHY-ETH-100M": 0.95, "SWITCH-5P": 3.20, "XCV-RS485": 0.85, "XCV-CAN": 0.90,
    "WIFI-M2": 8.40, "LTE-CAT4": 14.50,
    "CAP-0402-100N": 0.004, "CAP-0402-1U": 0.006, "CAP-0603-10U": 0.02, "CAP-EL-470U": 0.14,
    "CAP-EL-1000U": 0.21, "RES-0402-10K": 0.002, "RES-0402-1K": 0.002, "RES-0603-0R": 0.003,
    "DIO-TVS-24V": 0.09, "IND-PWR-4U7": 0.12, "IND-PWR-10U": 0.16, "LED-GRN": 0.03, "XTAL-25M": 0.18,
    "XTAL-32K": 0.12,
    "CON-RJ45-SH": 0.95, "CON-RJ45-2X": 2.10, "CON-TB-8P": 0.85, "CON-TB-16P": 1.50, "CON-USB-C": 0.45,
    "CON-DC-JACK": 0.35, "CON-FFC-30P": 0.40, "CON-POE-MAG": 2.30, "CON-SMA": 0.90, "CON-SIM": 0.30,
    "PCB-CORE-6L": 2.20, "PCB-MAIN-8L": 5.40, "PCB-MAIN-10L": 7.60, "PCB-IO-4L": 2.10, "PCB-VIS-10L": 6.90,
    "PCB-CTL-8L": 5.20, "PCB-PSU-2L": 1.10, "PCB-PSU-4L": 1.90, "PCB-CAM-4L": 1.40, "PCB-COM-6L": 2.60,
    "ENC-AL-S-BASE": 3.60, "ENC-AL-S-COVER": 2.40, "ENC-AL-M-BASE": 4.80, "ENC-AL-M-COVER": 3.10,
    "ENC-RUG-BASE": 7.90, "ENC-RUG-COVER": 5.20, "ENC-VIS-HOUSING": 6.20, "ENC-VIS-WINDOW": 2.10,
    "ENC-GASKET-KIT": 0.55, "ENC-PC-S": 1.20, "ENC-PC-M": 1.60, "ENC-DIN-RAIL-CLIP": 0.30,
    "HS-AL-40": 1.10, "HS-AL-60": 1.80, "HS-CU-30": 2.40, "FAN-40": 1.90,
    "XFMR-60W": 3.90, "XFMR-120W": 6.20, "XFMR-POE": 1.70, "BRIDGE-RECT": 0.41, "MOSFET-100V": 0.64,
    "CAP-BULK-400V": 1.10, "FUSE-5A": 0.22, "OPTO-ISO": 0.38, "PFC-CTRL": 1.35, "CMC-PWR": 0.85,
    "CBL-PWR-2C": 0.80, "CBL-IO-12C": 2.10, "CBL-COAX-RF": 0.70, "CBL-CAM-MIPI": 1.10,
    "WIRE-18AWG": 0.12, "WIRE-22AWG": 0.09,
    "SEN-CMOS-2MP": 6.80, "SEN-CMOS-5MP": 14.50, "LENS-M12-4MM": 2.20, "LENS-M12-8MM": 3.10,
    "LENS-HOLDER": 0.60, "IR-FILTER": 0.90, "IR-LED-850": 0.25,
    "SCR-M3-6": 0.02, "SCR-M3-10": 0.025, "SCR-M4-8": 0.03, "CLIP-CABLE": 0.04, "BRKT-DIN": 0.45,
    "BRKT-WALL": 0.85,
}

# Microcontrollers and SoCs are fixed anchors, not drawn from ranges.
# (id, name, supplier, price, weight, lead time, status, description)
SEMICONDUCTORS = [
    ("MCU-X100", "NovaChip MCU X100", "SUP-NOVA", 15.00, 0.002, 70, "EOL_ANNOUNCED",
     "32-bit industrial microcontroller. End-of-life announced by supplier."),
    ("MCU-X200", "NovaChip MCU X200", "SUP-NOVA", 17.70, 0.002, 84, "ACTIVE",
     "Next-generation pin-compatible successor to MCU-X100."),
    ("MCU-X150", "Crescent MCU X150", "SUP-CRES", 16.20, 0.002, 98, "ACTIVE",
     "Second-source microcontroller; firmware port required."),
    ("MCU-R50", "Atlas MCU R50", "SUP-ATLAS", 6.40, 0.001, 56, "ACTIVE", "Low-power I/O microcontroller."),
    ("MCU-K300", "Crescent MCU K300", "SUP-CRES", 11.80, 0.002, 63, "ACTIVE", "Application microcontroller."),
    ("MCU-K310", "Crescent MCU K310", "SUP-CRES", 13.40, 0.002, 63, "ACTIVE", "Networking microcontroller."),
    ("SOC-V700", "Crescent Vision SoC V700", "SUP-CRES", 16.50, 0.004, 77, "ACTIVE", "Vision processing SoC."),
    ("SOC-V710", "Crescent Vision SoC V710", "SUP-CRES", 21.00, 0.004, 77, "ACTIVE", "Vision processing SoC, Gen 2."),
]

# (id, name, processing cost, [(child, qty)])
ASSEMBLIES: list[tuple[str, str, float, list[tuple[str, float]]]] = [
    # --- Assemblies that contain MCU-X100 -----------------------------------
    ("SUB-C100", "MCU Core Module", 3.20, [
        ("MCU-X100", 1), ("MEM-D4-4G", 1), ("FLS-EM-16G", 1), ("PMIC-100", 1), ("PCB-CORE-6L", 1),
        ("CAP-0402-100N", 18), ("RES-0402-10K", 12), ("XTAL-25M", 1)]),
    ("ASM-A100", "Main Controller Board", 6.50, [
        ("SUB-C100", 1), ("PCB-MAIN-8L", 1), ("PHY-ETH-1G", 1), ("CON-RJ45-SH", 2), ("CON-USB-C", 1),
        ("LDO-3V3", 2), ("BUCK-5A", 1), ("CAP-0603-10U", 10), ("RES-0402-1K", 16), ("IND-PWR-4U7", 2),
        ("LED-GRN", 2), ("HS-AL-40", 1)]),
    ("ASM-A200", "Dual-Core Controller Board", 9.80, [
        ("SUB-C100", 2), ("PCB-MAIN-10L", 1), ("PHY-ETH-1G", 2), ("SWITCH-5P", 1), ("CON-RJ45-2X", 1),
        ("BUCK-10A", 1), ("LDO-1V8", 2), ("CAP-0603-10U", 16), ("RES-0402-1K", 24), ("IND-PWR-10U", 2),
        ("HS-AL-60", 1)]),
    ("ASM-B300", "I/O Expansion Board", 4.10, [
        ("MCU-X100", 1), ("PCB-IO-4L", 1), ("XCV-RS485", 2), ("CON-TB-8P", 2), ("OPTO-ISO", 8),
        ("DIO-TVS-24V", 4), ("CAP-0402-100N", 12), ("RES-0603-0R", 8)]),
    ("SUB-V410", "Vision Compute Module", 5.40, [
        ("SUB-C100", 1), ("SOC-V700", 1), ("MEM-D4-8G", 1), ("FLS-EM-32G", 1), ("PCB-VIS-10L", 1),
        ("PMIC-200", 1), ("CAP-0402-1U", 24)]),
    ("ASM-V400", "Vision Processing Board", 7.20, [
        ("SUB-V410", 1), ("PCB-CTL-8L", 1), ("CON-FFC-30P", 2), ("PHY-ETH-1G", 1), ("CON-POE-MAG", 1),
        ("HS-CU-30", 1), ("FAN-40", 1)]),
    # --- Other controller / I/O boards --------------------------------------
    ("SUB-K110", "Compute Core Module K", 3.40, [
        ("MCU-K300", 1), ("MEM-D4-4G", 1), ("FLS-EM-16G", 1), ("PMIC-100", 1), ("PCB-CORE-6L", 1),
        ("CAP-0402-100N", 18), ("XTAL-25M", 1)]),
    ("ASM-K100", "Compact Controller Board", 6.10, [
        ("SUB-K110", 1), ("PCB-MAIN-8L", 1), ("PHY-ETH-100M", 1), ("CON-RJ45-SH", 1), ("CON-USB-C", 1),
        ("LDO-3V3", 2), ("HS-AL-40", 1)]),
    ("ASM-K200", "Gateway Controller Board", 8.90, [
        ("MCU-K310", 1), ("MEM-D4-8G", 1), ("FLS-EM-32G", 1), ("PCB-CTL-8L", 1), ("PHY-ETH-1G", 2),
        ("SWITCH-5P", 1), ("CON-RJ45-2X", 1), ("BUCK-10A", 1), ("HS-AL-60", 1)]),
    ("SUB-R110", "I/O Core Module", 2.10, [
        ("MCU-R50", 1), ("EEP-64K", 1), ("PCB-IO-6L", 1), ("XTAL-32K", 1), ("CAP-0402-100N", 10)]),
    ("ASM-R100", "Digital I/O Board", 3.60, [
        ("SUB-R110", 1), ("CON-TB-16P", 2), ("OPTO-ISO", 16), ("DIO-TVS-24V", 8), ("RES-0603-0R", 16)]),
    ("ASM-R200", "Analog I/O Board", 4.20, [
        ("SUB-R110", 1), ("CON-TB-8P", 2), ("XCV-CAN", 1), ("CAP-0603-10U", 12), ("RES-0402-1K", 20)]),
    ("ASM-C300", "Communication Board", 3.80, [
        ("PCB-COM-6L", 1), ("XCV-RS485", 1), ("XCV-CAN", 1), ("CON-DB9", 2), ("CON-M12-4P", 1)]),
    ("ASM-V500", "Vision Board Gen 2", 7.90, [
        ("SOC-V710", 1), ("MEM-D4-8G", 1), ("FLS-EM-32G", 1), ("PCB-VIS-12L", 1), ("PMIC-200", 1),
        ("HS-CU-30", 1), ("CON-FFC-30P", 2)]),
    # --- Power ---------------------------------------------------------------
    ("PSU-24V", "24 V Power Supply Assembly", 2.80, [
        ("PCB-PSU-2L", 1), ("XFMR-60W", 1), ("BRIDGE-RECT", 1), ("MOSFET-100V", 2), ("CAP-BULK-400V", 1),
        ("FUSE-5A", 1), ("CMC-PWR", 1), ("CON-DC-JACK", 1)]),
    ("PSU-48V", "48 V Power Supply Assembly", 3.60, [
        ("PCB-PSU-4L", 1), ("XFMR-120W", 1), ("BRIDGE-RECT", 1), ("MOSFET-100V", 4), ("CAP-BULK-400V", 2),
        ("PFC-CTRL", 1), ("FUSE-5A", 1), ("CMC-PWR", 1)]),
    ("PSU-12V", "12 V Power Supply Assembly", 2.20, [
        ("PCB-PSU-2L", 1), ("XFMR-60W", 1), ("BRIDGE-RECT", 1), ("MOSFET-100V", 1), ("CAP-EL-470U", 2),
        ("FUSE-5A", 1)]),
    ("PSU-POE", "PoE Power Module", 2.40, [
        ("PCB-PSU-2L", 1), ("XFMR-POE", 1), ("MOSFET-100V", 2), ("CAP-EL-1000U", 1), ("EFUSE-24V", 1)]),
    # --- Enclosures ----------------------------------------------------------
    ("ENC-ASM-S", "Small Enclosure Assembly", 1.60, [
        ("ENC-AL-S-BASE", 1), ("ENC-AL-S-COVER", 1), ("ENC-GASKET-KIT", 1), ("SCR-M3-6", 8),
        ("ENC-DIN-RAIL-CLIP", 1)]),
    ("ENC-ASM-M", "Medium Enclosure Assembly", 2.10, [
        ("ENC-AL-M-BASE", 1), ("ENC-AL-M-COVER", 1), ("ENC-GASKET-KIT", 1), ("SCR-M3-10", 10), ("BRKT-DIN", 1)]),
    ("ENC-ASM-L", "Large Enclosure Assembly", 2.80, [
        ("ENC-AL-L-BASE", 1), ("ENC-AL-L-COVER", 1), ("ENC-GASKET-KIT", 1), ("SCR-M4-8", 12),
        ("BRKT-WALL", 1), ("FAN-60", 1)]),
    ("ENC-ASM-RUG", "Rugged Enclosure Assembly", 3.40, [
        ("ENC-RUG-BASE", 1), ("ENC-RUG-COVER", 1), ("ENC-GASKET-KIT", 2), ("SCR-M4-8", 16), ("BRKT-WALL", 1)]),
    ("ENC-ASM-VIS", "Vision Housing Assembly", 2.60, [
        ("ENC-VIS-HOUSING", 1), ("ENC-VIS-WINDOW", 1), ("ENC-GASKET-KIT", 1), ("SCR-M3-6", 6), ("BRKT-WALL", 1)]),
    ("ENC-ASM-PC", "Polycarbonate Enclosure Assembly", 1.20, [
        ("ENC-PC-S", 1), ("ENC-PC-M", 1), ("SCR-M3-6", 4), ("ENC-DIN-RAIL-CLIP", 1)]),
    # --- Harnesses, radios, cameras -----------------------------------------
    ("HRN-PWR", "Power Harness", 0.90, [("CBL-PWR-2C", 1), ("WIRE-18AWG", 2), ("CLIP-CABLE", 2)]),
    ("HRN-IO", "I/O Harness", 1.20, [("CBL-IO-12C", 1), ("WIRE-22AWG", 3), ("CLIP-CABLE", 3)]),
    ("MOD-LTE", "LTE Module Assembly", 2.60, [
        ("LTE-CAT4", 1), ("CON-SIM", 1), ("CON-SMA", 2), ("CBL-COAX-RF", 2), ("PCB-COM-6L", 1)]),
    ("MOD-WIFI", "Wi-Fi Module Assembly", 1.80, [("WIFI-M2", 1), ("CON-SMA", 2), ("CBL-COAX-RF", 2)]),
    ("CAM-2MP", "2 MP Camera Module", 3.10, [
        ("SEN-CMOS-2MP", 1), ("LENS-M12-4MM", 1), ("LENS-HOLDER", 1), ("IR-FILTER", 1), ("PCB-CAM-4L", 1),
        ("CBL-CAM-MIPI", 1)]),
    ("CAM-5MP", "5 MP Camera Module", 3.90, [
        ("SEN-CMOS-5MP", 1), ("LENS-M12-8MM", 1), ("LENS-HOLDER", 1), ("IR-FILTER", 1), ("IR-LED-850", 4),
        ("PCB-CAM-4L", 1), ("CBL-CAM-MIPI", 1)]),
]

PACK = {
    "S": [("BOX-S", 1), ("FOAM-S", 1), ("LBL-RATING", 1), ("LBL-SERIAL", 1), ("DOC-QSG", 1)],
    "M": [("BOX-M", 1), ("FOAM-M", 1), ("LBL-RATING", 1), ("LBL-SERIAL", 1), ("DOC-QSG", 1)],
    "L": [("BOX-L", 1), ("FOAM-M", 2), ("LBL-RATING", 1), ("LBL-SERIAL", 1), ("DOC-QSG", 1)],
}

EDGE, GATEWAY, VISION, SMART_IO = "Edge Control", "Industrial Gateway", "Vision System", "Smart I/O"

# Finished goods that use MCU-X100.
# (id, name, family, US price, pack, children, base monthly demand, FG stock days, margin group)
# Margin groups: "A" drops below target with MCU-X200 alone, "B" only in the
# compound scenario, "C" stays above target in both.
AFFECTED_PRODUCTS = [
    ("P100", "Edge Controller", EDGE, 169.00, "S",
     [("ASM-A100", 1), ("PSU-24V", 1), ("ENC-ASM-S", 1), ("HRN-PWR", 1)], 430, 40, "C"),
    ("P110", "Edge Controller Lite", EDGE, 129.00, "S",
     [("ASM-A100", 1), ("PSU-12V", 1), ("ENC-ASM-PC", 1)], 380, 45, "C"),
    ("P120", "Edge Controller Plus", EDGE, 249.00, "M",
     [("ASM-A200", 1), ("PSU-24V", 1), ("ENC-ASM-M", 1), ("HRN-PWR", 1), ("HRN-IO", 1)], 250, 14, "B"),
    ("P300", "Edge Controller Pro", EDGE, 329.00, "M",
     [("ASM-A200", 1), ("ASM-B300", 2), ("PSU-48V", 1), ("ENC-ASM-M", 1), ("HRN-PWR", 1), ("HRN-IO", 2)],
     190, 6, "A"),
    ("P200", "Industrial Gateway", GATEWAY, 249.00, "M",
     [("ASM-A200", 1), ("MOD-WIFI", 1), ("PSU-24V", 1), ("ENC-ASM-M", 1), ("HRN-PWR", 1)], 300, 12, "A"),
    ("P210", "Industrial Gateway LTE", GATEWAY, 269.00, "M",
     [("ASM-A200", 1), ("MOD-LTE", 1), ("PSU-24V", 1), ("ENC-ASM-M", 1), ("HRN-PWR", 1)], 230, 35, "C"),
    ("P220", "Rugged Industrial Gateway", GATEWAY, 289.00, "L",
     [("ASM-A100", 1), ("ASM-B300", 1), ("MOD-LTE", 1), ("PSU-48V", 1), ("ENC-ASM-RUG", 1), ("HRN-PWR", 1),
      ("HRN-IO", 1)], 120, 38, "C"),
    ("P230", "Compact Gateway", GATEWAY, 169.00, "S",
     [("ASM-A100", 1), ("PSU-POE", 1), ("ENC-ASM-S", 1)], 290, 42, "C"),
    ("P500", "Smart I/O Gateway", GATEWAY, 299.00, "M",
     [("ASM-A100", 1), ("ASM-B300", 2), ("PSU-24V", 1), ("ENC-ASM-M", 1), ("HRN-IO", 2)], 200, 10, "A"),
    ("P410", "Vision Hub", VISION, 229.00, "M",
     [("ASM-V400", 1), ("CAM-2MP", 1), ("PSU-POE", 1), ("ENC-ASM-VIS", 1)], 210, 9, "B"),
    ("P420", "Vision Hub Pro", VISION, 349.00, "L",
     [("ASM-V400", 1), ("CAM-5MP", 2), ("PSU-24V", 1), ("ENC-ASM-VIS", 1), ("HRN-PWR", 1)], 95, 30, "C"),
    ("P430", "Vision Sensor Node", VISION, 219.00, "S",
     [("ASM-V400", 1), ("CAM-2MP", 1), ("PSU-POE", 1), ("ENC-ASM-PC", 1)], 150, 36, "C"),
]

# Current gross margin for margin group "A" products (fraction).
GROUP_A_MARGIN = {"P300": 0.2180, "P500": 0.2120, "P200": 0.2100}

# Products where MCU-X200 is not yet approved (product-level override).
VALIDATION_REQUIRED = {
    "P300": "Dual-core board draws more current with MCU-X200; power-rail margin must be re-verified.",
    "P410": "Vision firmware timing depends on MCU-X100 clock tree; requires re-validation.",
    "P420": "Vision firmware timing depends on MCU-X100 clock tree; requires re-validation.",
    "P500": "I/O expansion firmware must be re-certified for functional-safety compliance.",
}

# Unaffected products: (id, name, family, board children, pack)
UNAFFECTED_NAMES = {
    EDGE: [("P130", "Edge Controller K1"), ("P140", "Edge Controller K2"), ("P150", "Edge Logic Unit"),
           ("P160", "Edge Controller Mini"), ("P170", "Edge Motion Controller"), ("P180", "Edge Safety Controller"),
           ("P190", "Edge Controller DIN")],
    GATEWAY: [("P240", "Fieldbus Gateway"), ("P250", "Protocol Gateway"), ("P260", "Cellular Router"),
              ("P270", "Edge Gateway X"), ("P280", "Serial Device Server"), ("P290", "Substation Gateway")],
    VISION: [("P440", "Vision Camera G2"), ("P450", "Vision Inspection Unit"), ("P460", "Vision Barcode Reader"),
             ("P470", "Vision Sensor G2"), ("P480", "Vision Line Scanner")],
    SMART_IO: [(f"P6{i}0", f"Smart I/O Module {name}") for i, name in enumerate(
        ["8DI", "8DO", "16DI", "16DO", "4AI", "4AO", "8AI", "Mixed", "Relay", "Counter"])]
    + [(f"P7{i}0", f"Smart I/O Remote {name}") for i, name in enumerate(
        ["R1", "R2", "R4", "R8", "Wireless", "PoE", "Compact", "Rugged", "Hub", "Bridge"])],
}

SEASONALITY = [1.00, 1.04, 0.96, 0.92, 1.02, 1.06, 1.03, 0.98, 1.01, 1.05, 0.97, 1.00]


# --------------------------------------------------------------------------
# Generator
# --------------------------------------------------------------------------


def _r2(x: float) -> float:
    return round(x + 0.0, 2)


def _r4(x: float) -> float:
    return round(x + 0.0, 4)


def _unaffected_children(rng: random.Random, family: str) -> tuple[list[tuple[str, float]], str]:
    if family == EDGE:
        board = rng.choice(["ASM-K100", "ASM-K100", "ASM-K200"])
        kids = [(board, 1), (rng.choice(["PSU-24V", "PSU-12V"]), 1),
                (rng.choice(["ENC-ASM-S", "ENC-ASM-M", "ENC-ASM-PC"]), 1), ("HRN-PWR", 1)]
        if rng.random() < 0.4:
            kids.append(("ASM-R100", 1))
        return kids, rng.choice(["S", "M"])
    if family == GATEWAY:
        kids = [("ASM-K200", 1), ("ASM-C300", 1), (rng.choice(["MOD-LTE", "MOD-WIFI"]), 1),
                (rng.choice(["PSU-24V", "PSU-48V"]), 1), (rng.choice(["ENC-ASM-M", "ENC-ASM-RUG", "ENC-ASM-L"]), 1),
                ("HRN-PWR", 1)]
        return kids, rng.choice(["M", "L"])
    if family == VISION:
        kids = [("ASM-V500", 1), (rng.choice(["CAM-2MP", "CAM-5MP"]), 1), (rng.choice(["PSU-POE", "PSU-24V"]), 1),
                ("ENC-ASM-VIS", 1)]
        return kids, "M"
    kids = [(rng.choice(["ASM-R100", "ASM-R200"]), 1), (rng.choice(["PSU-12V", "PSU-24V", "PSU-POE"]), 1),
            ("ENC-ASM-PC", 1), ("HRN-IO", 1)]
    if rng.random() < 0.3:
        kids.append(("ASM-C300", 1))
    return kids, "S"


def _price_ending(x: float) -> float:
    """Round up to a list price ending in .00, in $10 steps below $1,000."""
    return float(math.ceil(x / 10.0) * 10 - 1)


def generate() -> Snapshot:
    rng = random.Random(SEED)
    snap = Snapshot()
    lane_of_supplier = {s[0]: s[4] for s in SUPPLIERS}

    snap.suppliers = [Supplier(sid, name, country, risk) for sid, name, country, risk, _ in SUPPLIERS]
    snap.shipping_lanes = [ShippingLane(lid, o, d, m, rate, "USD") for lid, o, d, m, rate in LANES]
    snap.material_price = [MaterialPrice(code, p, "USD", PRICE_EFFECTIVE) for code, p in MATERIALS]

    items: list[ItemMaster] = []
    supplier_parts: list[SupplierPart] = []
    exposures: list[MaterialExposure] = []

    def add_purchased(pid, name, supplier, price, weight, lead, status, description, category):
        items.append(ItemMaster(pid, name, "COMPONENT", None, description or category, 0.0, _r4(weight), status))
        supplier_parts.append(SupplierPart(
            supplier_id=supplier, part_id=pid, supplier_part_number=f"{supplier[4:]}-{pid}",
            current_unit_price=price, lead_time_days=lead,
            minimum_order_qty=2500 if price >= 5 else 5000 if price >= 0.5 else 20000,
            status=status, shipping_lane_id=lane_of_supplier[supplier]))

    for pid, name, supplier, price, weight, lead, status, desc in SEMICONDUCTORS:
        add_purchased(pid, name, supplier, price, weight, lead, status, desc, "Microcontroller")

    for category, supplier, (pmin, pmax), (wmin, wmax), mats, parts in COMPONENT_CATEGORIES:
        for pid, name in parts:
            weight = rng.uniform(wmin, wmax)
            drawn = _r2(rng.uniform(pmin, pmax)) if pmax >= 0.3 else _r4(rng.uniform(pmin, pmax))
            price = PRICE_OVERRIDES.get(pid, drawn)
            lead = rng.choice([28, 35, 42, 56, 63, 70])
            add_purchased(pid, name, supplier, max(price, 0.001), weight, lead, "ACTIVE", "", category)
            for code, (mmin, mmax) in mats.items():
                kg = rng.uniform(mmin, mmax)
                if kg > 0:
                    exposures.append(MaterialExposure(pid, code, _r4(min(kg, weight * 0.9)) or 0.0001))

    edges: list[BomEdge] = []

    def add_edges(parent: str, children: list[tuple[str, float]]) -> None:
        for child, qty in children:
            edges.append(BomEdge(parent, child, float(qty), "EA", BOM_EFFECTIVE_FROM, None))

    for aid, name, proc, children in ASSEMBLIES:
        items.append(ItemMaster(aid, name, "ASSEMBLY", None, f"{name} (in-house assembly)", proc, 0.0, "ACTIVE"))
        add_edges(aid, children)

    # Finished goods: base processing is calibrated after the roll-up below.
    fg_specs: list[dict] = []
    for pid, name, family, price, pack, kids, qty, fg_days, group in AFFECTED_PRODUCTS:
        fg_specs.append(dict(id=pid, name=name, family=family, price=price, children=kids + PACK[pack],
                             monthly=qty, fg_days=fg_days, group=group, affected=True))
    for family, names in UNAFFECTED_NAMES.items():
        for pid, name in names:
            kids, pack = _unaffected_children(rng, family)
            fg_specs.append(dict(id=pid, name=name, family=family, price=None, children=kids + PACK[pack],
                                 monthly=rng.randrange(60, 520, 10), fg_days=rng.randrange(20, 75),
                                 group="U", affected=False, target_margin=rng.uniform(0.26, 0.42),
                                 processing=rng.uniform(8.0, 22.0)))
    for spec in fg_specs:
        add_edges(spec["id"], spec["children"])

    # Provisional FG rows (zero processing) to measure the rolled-up child cost.
    provisional = [ItemMaster(s["id"], s["name"], "FINISHED_GOOD", s["family"], "", 0.0, 0.0, "ACTIVE")
                   for s in fg_specs]
    snap.item_master = items + provisional
    snap.bom_edges = edges
    snap.supplier_parts = supplier_parts
    snap.material_exposure = exposures
    index = DataIndex.build(snap, AS_OF)
    base_engine = CostEngine(index)
    rep_engine = CostEngine(index, CostParams(substitutions={ANCHOR_PART: REPLACEMENT_PART}))
    compound_engine = CostEngine(index, COMPOUND)

    fg_items: list[ItemMaster] = []
    prices: list[ProductPrice] = []
    for spec in fg_specs:
        pid = spec["id"]
        child_cost = base_engine.cost(pid).total
        if spec["affected"]:
            price = spec["price"]
            rep_pts = (rep_engine.cost(pid).total - child_cost) / price
            cmp_pts = (compound_engine.cost(pid).total - child_cost) / price
            if spec["group"] == "A":
                margin = GROUP_A_MARGIN[pid]
                assert MARGIN_TARGET <= margin < MARGIN_TARGET + rep_pts, pid
            elif spec["group"] == "B":
                # Midway between "below with compound" and "below with replacement".
                margin = MARGIN_TARGET + (rep_pts + cmp_pts) / 2
            else:
                margin = MARGIN_TARGET + cmp_pts + 0.03 + rng.uniform(0.0, 0.07)
            processing = _r2(price * (1 - margin) - child_cost)
            if processing < 4.0:
                raise ValueError(f"{pid}: price {price} too low for margin {margin:.3f} (processing {processing})")
        else:
            processing = _r2(spec["processing"])
            price = _price_ending((child_cost + processing) / (1 - spec["target_margin"]))
        spec["processing"] = processing
        fg_items.append(ItemMaster(pid, spec["name"], "FINISHED_GOOD", spec["family"],
                                   f"{spec['family']} product", processing, 0.0, "ACTIVE"))
        prices.append(ProductPrice(pid, "US", price, "USD", PRICE_EFFECTIVE))
        spec["price"] = price

    snap.item_master = items + fg_items
    snap.product_price = prices

    # Demand: scale the affected products' base volumes to the revenue target.
    months = horizon_months(AS_OF, DEMAND_MONTHS)
    horizon = months[:HORIZON_MONTHS]
    affected = [s for s in fg_specs if s["affected"]]
    raw_revenue = sum(s["price"] * s["monthly"] * sum(SEASONALITY[:HORIZON_MONTHS]) for s in affected)
    scale = TARGET_REVENUE_EXPOSURE / raw_revenue
    demand: list[ProductDemand] = []
    for spec in fg_specs:
        base = spec["monthly"] * (scale if spec["affected"] else 1.0)
        spec["horizon_qty"] = 0.0
        for i, month in enumerate(months):
            qty = float(round(base * SEASONALITY[i]))
            open_share = 0.62 if i == 0 else 0.34 if i == 1 else 0.12 if i == 2 else 0.0
            demand.append(ProductDemand(spec["id"], month, qty, float(round(qty * open_share))))
            if month in horizon:
                spec["horizon_qty"] += qty
    snap.product_demand = demand

    # Inventory.
    days = horizon_days(horizon)
    usage = {u.product_id: u.effective_component_qty for u in trace_in_memory(index, ANCHOR_PART).products}
    mcu_daily = sum(usage[s["id"]] * s["horizon_qty"] for s in affected) / days
    mcu_available = math.ceil(TARGET_COVERAGE_DAYS * mcu_daily)
    inventory: list[Inventory] = []

    def stock(item_id: str, location: str, available: float, allocated: float) -> None:
        inventory.append(Inventory(item_id, location, float(available + allocated), float(allocated),
                                   float(available), SNAPSHOT_DATE))

    plant_share = round(mcu_available * 0.78)
    stock(ANCHOR_PART, "US-AUS-PLANT", plant_share, 1200)
    stock(ANCHOR_PART, "US-DAL-DC", mcu_available - plant_share, 0)
    stock(REPLACEMENT_PART, "US-AUS-PLANT", 400, 0)  # engineering samples only
    for it in items:
        if it.item_type == "COMPONENT" and it.item_id not in (ANCHOR_PART, REPLACEMENT_PART, "MCU-X150"):
            stock(it.item_id, "US-AUS-PLANT", float(rng.randrange(800, 60000, 50)), float(rng.randrange(0, 800, 50)))
    for spec in fg_specs:
        daily = spec["horizon_qty"] / days
        stock(spec["id"], "US-DAL-DC", float(round(daily * spec["fg_days"])), 0)
    snap.inventory = inventory

    # Alternates.
    snap.alternate_parts = [
        AlternatePart(ANCHOR_PART, REPLACEMENT_PART, "APPROVED", 0,
                      "Pin-compatible successor recommended by NovaChip; approved for standard configurations."),
        *[AlternatePart(ANCHOR_PART, REPLACEMENT_PART, "VALIDATION_REQUIRED", 45, note, product_id=pid)
          for pid, note in VALIDATION_REQUIRED.items()],
        AlternatePart(ANCHOR_PART, "MCU-X150", "NOT_APPROVED", 120,
                      "Second source from Crescent Semiconductor; requires firmware port and full qualification."),
        AlternatePart("MCU-K300", "MCU-K310", "APPROVED", 0, "Higher-performance variant; drop-in."),
        AlternatePart("SOC-V700", "SOC-V710", "VALIDATION_REQUIRED", 60, "Gen 2 vision SoC; new camera pipeline."),
    ]

    snap.change_events = [
        ChangeEvent("EVT-1001", "SUPPLIER_PRICE_INCREASE", "SUP-SUMM", "CON-RJ45-SH", date(2026, 9, 18), None, None,
                    None, None, "MONITORING", "Summit Interconnect connector price increase",
                    "Summit Interconnect announced a 6% price increase on shielded RJ45 jacks from November 1, 2026."),
        ChangeEvent("EVT-1002", "MATERIAL_PRICE_CHANGE", None, None, date(2026, 9, 22), None, None, None, None,
                    "MONITORING", "Copper price trending upward",
                    "LME copper is up 8% month-over-month; component suppliers signal surcharge adjustments."),
        ChangeEvent("EVT-1003", "FREIGHT_CHANGE", None, None, date(2026, 9, 24), None, None, None, None,
                    "MONITORING", "Taiwan to US ocean freight increase",
                    "Carriers on the Taiwan to United States ocean lane announced a general rate increase for Q4."),
    ]
    add_operations_data(snap)
    return snap
