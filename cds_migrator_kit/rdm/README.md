# Migration model manual

## Dump users

! Attention If you need to dump the users from legacy DB or you need to process the people collection

https://gitlab.cern.ch/cds-team/production_scripts/-/blob/master/cds-rdm/migration/dump_users.py?ref_type=heads

## Dump a subset of records on legacy

on webnode: `cds-migration-01`

```bash
inveniomigrator dump records -q '980:INTNOTECMSPUBL 980:NOTE -980:DELETED' --file-prefix cms-notes --chunk-size=1000

```

## Define transforming models and rules resolution

You can adapt XML processing to different subsets of records by implementing different data models for each subset (f.e. collection).
Let's take CMS notes as an example:

```python

class CMSNote(CdsOverdo):
    """Translation Index for CDS Books."""

    __query__ = (
        '980__:INTNOTECMSPUBL 980__:NOTE'
    )

    __model_ignore_keys__ = {}

    _default_fields = {}



model = CMSNote(bases=(),
                entry_point_group="cds_rdm.migrator.rules"
                )

```

**query** - defines the MARC fields to which specific record should match. Attention: It does not recognise regexes that are used to specify the collection query in the admin interface of legacy CDS.

\***\*model_ignore_keys\*\*** - set of keys to be ignored for this data model - fields will not be migrated

**bases** - by defining bases of models you can specify a parent model which fits all the subsets of records (f.e. 245 - title field MARC to JSON translation could be the same for all the models)

**entry_point_group** - reference to where the model should lookup for the set of the MARC translation rules, see the entrypoints below.

After defining your model and set of rules,you have to register them in the entrypoints of your application, in setup.cfg:

```editorconfig

[options.entry_points]
cds_migrator_kit.migrator.models =
    cms_note = cds_rdm.migration.transform.models.note:model
cds_migrator_kit.migrator.rules =
    base = cds_rdm.migration.transform.xml_processing.rules

```

## Full migration workflow of one collection

### To visualise the errors (locally):

```shell
gunicorn -b :8080 --timeout 120 --graceful-timeout 60 cds_migrator_kit.app:app --reload --log-level debug --capture-output --access-logfile '-' --error-logfile '-'
```

### Legacy

This is the recipe on how to dump the metadata and files. For local tests it is not necessary to do it often, especially for files which are static.
It makes sense to dump metadata if any changes are applied on legacy

```shell
ssh cds-migration-01 # inveniomigrator tool installed here
cd /tmp/current-collection-dump
inveniomigrator dump records -q '037__:CERN-STUDENTS-Note-* -980:DELETED' --file-prefix summer-studends-notes --latest-only --chunk-size=1000

cd /eos/media/cds/cds-rdm/dev/migration/summer-student-notes/dump
kinit cdsrdmeosdev
cp /tmp/current-collection-dump/* .


# copy over all files to temporary location
ipython
# run script available in /scripts/copy_collection_files.py
# destination_prefix = "/eos/media/cds/cds-rdm/dev/migration/summer-student-notes/files"
# working_dir = "/eos/media/cds/cds-rdm/dev/migration/summer-student-notes"
# json_dump_dir = "/eos/media/cds/cds-rdm/dev/migration/summer-student-notes/dump"
```

Identify and dump duplicated records i.e. records with same title, description and file
checksums (excluding deleted files) on EOS. If duplicates found, then we keep the recid
that has restricted files or if not any, then the first one from the list.

In a python shell run the script `scripts/dump_legacy_recids_to_redirect.py`.

#### How to mount eos locally on MAC (to copy over the dumps and files)

1. Go to Finder icon on your dock
2. right click to get the contextual menu
3. choose connect to server
4. type `https://cernbox.cern.ch/cernbox/webdav/eos/media/cds/cds-rdm/dev/migration`
5. click connect
6. use eos account dev credentials

### Openshift migration pod

#### Collect and dump affiliation mapping

In order to collect all affiliations from the collection dump folder run the following
command pointing to the `cds_migrator_kit.rdm.data.summer_student_reports.dump`
folder:

```
invenio migration affiliations run --filepath /path/to/cds_migrator_kit/rdm/migration/data/summer_student_reports/dump
```

This will collect and check each affiliation against the ROR organization API, and store them in the `cds_rdm.legacy.models.CDSMigrationAffiliationMapping` table.

The model is then used during record migration to normalize the affiliation content following the below principles
to map the legacy input to a normalized value:

1. If curated affiliation that might or not have a ROR ID exists then this value is used.
2. A ROR exact match
3. A ROR not exact match with a level of confidence of >= 90%. This will also flag the
   record for further curation to validate the value.
4. The legacy affiliation value, and flag the record.

#### Community id dump

Dump the community id to migration `streams.yaml`(if the slug exists then it will read and dump the id only):

```shell
invenio migration community dump --slug 'sspn' --title 'Summer Student Project Notes' --filepath /path/to/cds_migrator_kit/rdm/migration/streams.yaml
```

#### Missing Users files

Make sure to add the user files required to be able to run the migration. The files can be found in `/eos/media/cds/cds-rdm/dev/migration/users/`. They should be stored in path indicated in the streams.yaml, the value that corresponds to the `record.transform.missing_users` key.

#### Records migration

Run the below command to migrate records in the created community from before:

```shell
invenio migration run
```

### Migrate the statistics for the successfully migrated records

When the `invenio migration run` command ends it will produce a `rdm_records_state.json` file which has linked information about the migrated records and the old system. The format will be similar to below:

```json
{
  "legacy_recid": "2884810",
  "parent_recid": "zts3q-6ef46",
  "parent_object_uuid": "155be22f-3038-49e0-9f17-9518eaac783a",
  "latest_version": "1mae4-skq89",
  "latest_version_object_uuid": "155be22f-3038-49e0-9f17-9518eaac783a",
  "versions": [
    {
      "new_recid": "1mae4-skq89",
      "version": 2,
      "files": [
        {
          "legacy_file_id": 1568736,
          "bucket_id": "155be22f-3038-49e0-9f17-9518eaac783a",
          "file_key": "Summer student program report.pdf",
          "file_id": "06cdb9d2-635f-4dbe-89fe-4b27afddeaa2",
          "size": "1690854"
        }
      ]
    }
  ]
}
```

- Open the `cds_migrator_kit/rdm/migration/stats/config.py` and

  - export the below 2 environmental variables
    - `CDS_MIGRATOR_KIT_SRC_SEARCH_HOSTS`: e.g `export CDS_MIGRATOR_KIT_SRC_SEARCH_HOSTS='[{"host": "os-cds-legacy.cern.ch", "url_prefix": "/os", "timeout": 30, "port": 443, "use_ssl": true, "verify_certs": false, "http_auth": ["LEGACY_PRODUCTION_OPENSEARCH_USERNAME", "<LEGACY_PRODUCTION_OPENSEARCH_PASSWORD>"]}]'`
      - you find the credentials for `LEGACY_PRODUCTION_OPENSEARCH_PASSWORD` by `tbag show LEGACY_PRODUCTION_OPENSEARCH_PASSWORD --hg cds`
      - you find the credentials for `LEGACY_PRODUCTION_OPENSEARCH_USERNAME` by `tbag show LEGACY_PRODUCTION_OPENSEARCH_USERNAME --hg cds`

- Open a shell and run the following commands

```bash
$ invenio migration stats run --filepath "path/to/file/of/rdm_records_state.json"
```

This will migrate only the raw statistic events. When all events are ingested to the new cluster then we will need to aggregate them.

To do so, you need to run after you have set the correct bookmark for each event:

on opensearch

```shell
DELETE /cds-rdm-stats-bookmarks

POST /cds-rdm-stats-bookmarks/_doc
{
  "date": "2000-06-26T15:56:05.755394",
  "aggregation_type": "file-download-agg"
}
POST /cds-rdm-stats-bookmarks/_doc
{
  "date": "2000-06-26T15:56:05.755394",
  "aggregation_type": "record-view-agg"
}
POST /cds-rdm-stats-bookmarks/_doc
{
  "date": "2000-06-26T15:56:05.755394",
  "aggregation_type": "stats_reindex"
}
```

```
from invenio_stats.tasks import aggregate_events

start_date = '2000-01-01'
end_date = '2024-12-01'

aggregations = ["record-view-agg", "file-download-agg"]
aggregate_events(aggregations)

from invenio_rdm_records.services.tasks import reindex_stats
stats_indices = [ "stats-record-view", "stats-file-download",]

reindex_stats(stats_indices)
```

visit https://migration-cds-rdm-dev.app.cern.ch for report

## Local rerun migration from clean state without setup everything again

If you want to cleanup a previous migration run without having to re setup everything
i.e not repopulating all vocabularies which takes a lot of time, then run the following
recipe:

- Cleanup db tables from pgadmin (**!!! ONLY ON DEV or local !!!**)

```sql
DELETE FROM rdm_versions_state;
DELETE FROM rdm_records_files;
DELETE FROM rdm_drafts_files;
DELETE FROM rdm_records_metadata;
DELETE FROM rdm_drafts_metadata;
DELETE FROM rdm_parents_metadata;
DELETE FROM communities_files;
DELETE FROM oaiserver_set;
DELETE FROM communities_metadata;
DELETE FROM files_objecttags;
DELETE FROM files_object;
DELETE FROM files_buckettags;
DELETE FROM files_bucket;
DELETE FROM files_files;
DELETE FROM pidstore_pid WHERE pid_type = 'lrecid';
DELETE FROM pidstore_pid WHERE pid_type = 'recid';
DELETE FROM pidstore_pid WHERE pid_type = 'doi';
DELETE FROM cds_clc_record_sync;
DELETE FROM cds_migration_legacy_records;
```

- Cleanup indexed documents from opensearch

```
POST /cds-rdm-dev-rdmrecords/_delete_by_query
{
  "query": {
    "match_all": {}
  }
}
POST /cds-rdm-dev-communities/_delete_by_query
{
  "query": {
    "match_all": {}
  }
}
```

- Rerun `invenio migration community dump --slug 'sspn' --title 'Summer Student Project Notes' --filepath /path/to/cds_migrator_kit/rdm/migration/streams.yaml`
- Rerun `invenio migration run`
