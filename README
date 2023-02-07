## Install poetry
```
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
```

> *All following commands will assume thar project are in the directory `/home/user/openapi`*

## Install dependencies
```
cd /home/user/openapi/backend/app
poetry install
```

## Set python module path
```
export PYTHONPATH=$PYTHONPATH:/<path>/openapi/backend/app
```

## Copy and edit .env
```
cp .env.example .env
```

## To start application, either:
```
cd /home/user/openapi/backend/app
poetry run python app/main.py
```
or
```
cd /home/user/openapi/backend/app/app
poetry run uvicorn main:app --host 0.0.0.0 --port 8000
```

## To start celery beat (celery scheduler)
```
cd /home/user/openapi/backend/app
celery -A app.main.celery beat -l debug
```

## To start celery workers (celery workers)
```
cd /home/user/openapi/backend/app
celery -A app.main.celery worker --loglevel=debug -Q cascade,sense,celery -c 1
```

## To start celery flower (celery monitoring web UI)
```
cd /home/user/openapi/backend/app
celery -A app.main.celery flower --port=5555
```



