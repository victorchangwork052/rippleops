# Third-Party Licenses

RippleOps uses permissively licensed open-source software. License texts for the
bundled UI libraries are in [`/LICENSES`](../LICENSES).

| Component | Purpose | License | Notice |
|---|---|---|---|
| Lucide (`lucide-react`) | Line icons | ISC | `LICENSES/lucide-react.LICENSE.txt` |
| React Flow (`@xyflow/react`) | BOM dependency graph | MIT | `LICENSES/xyflow_react.LICENSE.txt` |
| Recharts | Charts | MIT | `LICENSES/recharts.LICENSE.txt` |
| Tailwind CSS | Styling | MIT | `LICENSES/tailwindcss.LICENSE.txt` |
| Next.js | Web framework | MIT | `LICENSES/next.LICENSE.txt` |
| class-variance-authority, clsx, tailwind-merge | Component styling utilities (shadcn/ui pattern) | Apache-2.0 / MIT / MIT | `LICENSES/` |
| shadcn/ui | Component patterns re-implemented in `apps/web/components/ui.tsx` | MIT | https://github.com/shadcn-ui/ui |
| Inter | Typeface, loaded via `next/font/google` | SIL Open Font License 1.1 | https://github.com/rsms/inter/blob/master/LICENSE.txt |
| FastAPI, Pydantic, Uvicorn | API | MIT / MIT / BSD-3-Clause | Installed packages' metadata |
| Google ADK, Google GenAI SDK, google-cloud-bigquery | Agent, Gemini and BigQuery clients | Apache-2.0 | Installed packages' metadata |
| pypdf | PDF text extraction | BSD-3-Clause | Installed package metadata |

No paid icon packs, unlicensed SVG assets, or third-party brand artwork are used.
Before production use, review the exact license texts of all dependency versions
included in the build.
