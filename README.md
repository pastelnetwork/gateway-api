# Pastel Gateway API


## API Changes from v1.2.1 to v2.0.0

### Cascade:
```
/api/v1/cascade/pastel_ticket_by_stored_file_hash          --> /api/v1/cascade/pastel_registration_ticket_from_stored_file_hash
```

### Sense:
```
/api/v1/sense/raw_output_file_by_registration_ticket       --> /api/v1/sense/raw_dd_result_file_from_registration_ticket
/api/v1/sense/parsed_output_file_by_registration_ticket    --> /api/v1/sense/parsed_dd_result_file_from_registration_ticket
/api/v1/sense/raw_output_file_by_activation_ticket         --> /api/v1/sense/raw_dd_result_file_from_activation_ticket
/api/v1/sense/parsed_output_file_by_activation_txid        --> /api/v1/sense/parsed_dd_result_file_from_activation_ticket
/api/v1/sense/raw_output_file_by_pastel_id                 --> /api/v1/sense/raw_dd_result_file_from_pastel_id
/api/v1/sense/parsed_output_file_by_pastel_id              --> /api/v1/sense/parsed_dd_result_file_from_pastel_id
/api/v1/sense/pastel_ticket_by_media_file_hash             --> /api/v1/sense/pastel_registration_ticket_from_media_file_hash
```

### NFT:    
```
/api/v1/nft/raw_dd_result_file_by_registration_ticket      --> /api/v1/nft/raw_dd_result_file_from_registration_ticket
/api/v1/nft/parsed_dd_result_file_by_registration_ticket   --> /api/v1/nft/parsed_dd_result_file_from_registration_ticket
/api/v1/nft/raw_dd_result_file_by_activation_ticket        --> /api/v1/nft/raw_dd_result_file_from_activation_ticket
/api/v1/nft/parsed_dd_result_file_by_activation_txid       --> /api/v1/nft/parsed_dd_result_file_from_activation_ticket
/api/v1/nft/raw_dd_result_file_by_pastel_id                --> /api/v1/nft/raw_dd_result_file_from_pastel_id
/api/v1/nft/parsed_dd_result_file_by_pastel_id             --> /api/v1/nft/parsed_dd_result_file_from_pastel_id
/api/v1/nft/pastel_ticket_by_media_file_hash               --> /api/v1/nft/pastel_registration_ticket_from_media_file_hash
```

# Setup

## Install poetry
```
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
```

> *All following commands will assume thar project are in the directory `/home/user/openapi`*

## Install dependencies
```
cd $HOME/gateway-api/backend/app
poetry install
```

## Set python module path
```
export PYTHONPATH=$PYTHONPATH:$HOME/gateway-api/backend/app
```

## Copy and edit .env
```
cp .env.example .env
```

## Gateway supports reading configuration from AWS Secret manager
```ini
AWS_SECRET_MANAGER_REGION="us-east-2"
AWS_SECRET_MANAGER_RDS_CREDENTIALS="evnet-gateway-api-db-credentials"
AWS_SECRET_MANAGER_RDS_PARAMETERS="gateway-api-db"
AWS_SECRET_MANAGER_SMTP_SECRETS="gateway-api-smtp"
AWS_SECRET_MANAGER_PASTEL_IDS="gateway-api-pastelids"
```

Where:
AWS_SECRET_MANAGER_RDS_CREDENTIALS should contain:
"username": "your_DB_username"
"password": "your_DB_password"

AWS_SECRET_MANAGER_RDS_PARAMETERS should contain:
"port": "your_DB_port",
"host": "your_DB_host"
"dbname": "your_DB_name"

AWS_SECRET_MANAGER_SMTP_SECRETS should contain:
"password": "your_SMTP_password"

AWS_SECRET_MANAGER_PASTEL_IDS is where gateway will store pastel ids for each user


## Start for local development
### Start API Server
```
cd $HOME/gateway-api/backend/app
poetry run python app/main.py
```
### Start celery beat (celery scheduler)
```
cd $HOME/gateway-api/backend/app
celery -A app.main.celery beat -l debug
```

### Start celery workers (celery workers)
```
cd $HOME/gateway-api/backend/app
celery -A app.main.celery worker --loglevel=debug -Q cascade,sense,nft,registration_helpers,scheduled_tools
```

### Start celery flower (celery monitoring web UI)
```
cd /home/user/openapi/backend/app
celery -A app.main.celery flower --port=5555
```

Or use shell scripts:
```shell
0-start-web-server.sh
1-start-celery-worker.sh
2-start-celery-registration-helpers.sh
3-start-celery-scheduled-tools.sh
4-start-celery-beat.sh
5-start-celery-flower.sh
```

## Start for production

Best way is to use systemd service files. Example files are in `systemd` directory.

You would need minimum 2 hosts, one for API server and celery workers to register and process tasks, and another for account manager:
### Host 1: API server and celery workers
* `systemd/psl-gateway-server.service`
* `systemd/psl-gateway-workers.service`
* `systemd/psl-gateway-registration-helpers.service`
* `systemd/psl-gateway-scheduled-tools.service`
* `systemd/psl-gateway-beat.service`


### Host 2: Account manager
* `systemd/psl-gateway-account-mananger.service`
* `systemd/psl-gateway-beat.service`

Config file (.env):
``` ini
REGISTRATION_FINISHER_ENABLED=False
REGISTRATION_RE_PROCESSOR_ENABLED=False
FEE_PRE_BURNER_ENABLED=False
TICKET_ACTIVATOR_ENABLED=False
REG_TICKETS_FINDER_ENABLED=False
WATCHDOG_ENABLED=False
ACCOUNT_MANAGER_ENABLED=True
```
