---
name: run-tests
description: Run the Django test suite. Use when asked to run tests, verify a fix, or check whether changes break anything.
---

Run the Django test suite from the correct directory:

```bash
cd companyapi && python manage.py test
```

To target a specific app:

```bash
cd companyapi && python manage.py test apps.<app_name>
```

To run a single test class or method:

```bash
cd companyapi && python manage.py test apps.<app_name>.tests.<ClassName>.<method_name>
```

If running inside Docker:

```bash
docker-compose exec web python manage.py test
```

Report the full output including any failures, errors, and the final pass/fail count.
