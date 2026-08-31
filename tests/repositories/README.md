# Repository integration tests

These tests use a dedicated MySQL database through SQLAlchemy's `mysql+asyncmy` driver.

Set `TEST_DATABASE_URL` before running the repository tests, for example:

```bash
export TEST_DATABASE_URL='mysql+asyncmy://USER:PASSWORD@127.0.0.1:3306/aiogrambot_test'
pytest tests/repositories -q
```

On Windows PowerShell:

```powershell
$env:TEST_DATABASE_URL = 'mysql+asyncmy://USER:PASSWORD@127.0.0.1:3306/aiogrambot_test'
pytest tests/repositories -q
```

The database must be a dedicated test database. Do not use the production database URL.

The fixture creates the ORM schema with `Base.metadata.create_all()` and creates a fresh SQLAlchemy session for each test. Test data is therefore isolated by the transaction used by each fixture invocation.
