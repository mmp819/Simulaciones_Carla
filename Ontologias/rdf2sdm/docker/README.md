# Docker test setup

## Preparation

Add the following line to the `/etc/hosts` file (note the hyphen before "com"):

    <server IP>       github-com smart-data-models.github-com raw.githubusercontent-com smartdatamodels-org

Note that the IP address should be external, loopback address (`127.0.0.1`) might not work.

Copy generated files `context.jsonld` and `schema.json` to the adequate local web server folders, e.g.:

- `/sdm/dataModel.ACDSi/master/context.jsonld` to `www/smart-data-models/dataModel.ACDSi/master`
- `dataModel.ACDSi/ACDSiMeasurement/schema.json` to `www/dataModel.ACDSi/ACDSiMeasurement/schema.json`

As in this local setup, the plain HTTP is used and repository hostname is made up, modify the `@context` in the `example-normalized.jsonld` so that it begins with `http://raw.githubusercontent-com/...` (note the hyphen before "com").

## Running the setup:

    cd docker
    docker compose up -d

## Uploading the example file:

    python ngsild_upload.py
