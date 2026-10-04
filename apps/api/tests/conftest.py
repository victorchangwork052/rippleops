import os

import pytest

# Tests always run against the deterministic local seed, never live services.
os.environ["DATA_BACKEND"] = "local"
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"


@pytest.fixture(scope="session")
def seed_repo():
    from app.db.repository import LocalRepository
    from app.seed.generator import AS_OF

    return LocalRepository(AS_OF)
