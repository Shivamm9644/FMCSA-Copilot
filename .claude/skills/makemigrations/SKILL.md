---
name: makemigrations
description: Run Django makemigrations + migrate after any models.py change, or before running tests when migrations may be stale.
---

After any model change, run both steps:

```bash
cd companyapi && python manage.py makemigrations && python manage.py migrate
```

If running inside Docker:

```bash
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
```

Report which migration files were created and which migrations were applied.
If no changes are detected, confirm migrations are already up to date.
