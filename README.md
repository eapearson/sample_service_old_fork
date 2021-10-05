# SampleService

Build status (master):
[![Build Status](https://travis-ci.org/kbase/sample_service.svg?branch=master)](https://travis-ci.org/kbase/sample_service)
[![Coverage Status](https://coveralls.io/repos/github/kbase/sample_service/badge.svg?branch=master)](https://coveralls.io/github/kbase/sample_service?branch=master)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/kbase/sample_service.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/kbase/sample_service/context:python)

This is a [KBase](https://kbase.us) module generated by the [KBase Software Development Kit (SDK)](https://github.com/kbase/kb_sdk).

You will need to have the SDK installed to use this module. [Learn more about the SDK and how to use it](https://kbase.github.io/kb_sdk_docs/).

You can also learn more about the apps implemented in this module from its [catalog page](https://narrative.kbase.us/#catalog/modules/SampleService) or its [spec file](SampleService.spec).

# Description

The Sample Service stores information regarding experimental samples taken from the environment.
It supports Access Control Lists for each sample, subsample trees, and modular metadata
validation.

The SDK API specification for the service is contained in the `SampleService.spec` file. An indexed
interactive version is
[also available](http://htmlpreview.github.io/?https://github.com/kbaseIncubator/sample_service/blob/master/SampleService.html).

# Setup and test

The Sample Service requires ArangoDB 3.5.1+ with RocksDB as the storage engine.

If Kafka notifications are enabled, the Sample Service requires Kafka 2.5.0+.

To run tests, MongoDB 3.6+ and the KBase Jars file repo are also required. Kafka is always
required to run tests.

See `.travis.yml` for an example of how to set up tests, including creating a `test.cfg` file
from the `test/test.cfg.example` file.

Once the dependencies are installed, run:

```
pipenv install --dev
pipenv shell
make test-sdkless
```

`kb-sdk test` does not currently pass. 


# Installation from another module

To use this code in another SDK module, call `kb-sdk install SampleService` in the other module's root directory.

# Help

You may find the answers to your questions in our [FAQ](https://kbase.github.io/kb_sdk_docs/references/questions_and_answers.html) or [Troubleshooting Guide](https://kbase.github.io/kb_sdk_docs/references/troubleshooting.html).

# Configuring the server

The server has several startup parameters beyond the standard SDK-provided parameters
that must be configured in the Catalog Service by a Catalog Service administrator in order
for the service to run. These are documented in the `deploy.cfg` file.

## Kafka Notification

The server may be configured to send notifications on events to Kafka - see the `deploy.cfg` file
for information. The events and their respective JSON message formats are:

### New sample or sample version

```
{'event_type': 'NEW_SAMPLE',
 'sample_id': <sample ID>,
 'sample_ver': <sample version>
 }
```

### Sample ACL change

```
{'event_type': 'ACL_CHANGE',
 'sample_id': <sample ID>
 }
```

### New data link

```
{'event_type': 'NEW_LINK',
 'link_id': <link ID>
 }
```

### Expired data link

```
{'event_type': 'EXPIRED_LINK',
 'link_id': <link ID>
 }
```

# API Error codes

Error messages returned from the API may be general errors without a specific structure to
the error string or messages that have error codes embedded in the error string. The latter
*usually* indicate that the user/client has sent bad input, while the former indicate a server
error. A message with an error code has the following structure:

```
Sample service error code <error code> <error type>: <message>
```

There is a 1:1 mapping from error code to error type; error type is simply a more readable
version of the error code. The error type **may change** for an error code, but the error code
for a specific error will not.

The current error codes are:
```
20000 Unauthorized
30000 Missing input parameter
30001 Illegal input parameter
30010 Metadata validation failed
40000 Concurrency violation
50000 No such user
50010 No such sample
50020 No such sample version
50030 No such sample node
50040 No such workspace data
50050 No such data link
60000 Data link exists for data ID
60010 Too many data links
100000 Unsupported operation
```

# Metadata validation

Each node in the sample tree accepted by the `create_sample` method may contain controlled and
user metadata. User metadata is not validated other than very basic size checks, while controlled
metadata is validated based on configured validation rules.

## All metadata

For all metadata, map keys are are limited to 256 characters and values are limited to 1024
characters. Keys may not contain any control characters, while values may contain tabs and
new lines.

## Controlled metadata

Controlled metadata is subject to validation - no metadata is allowed that does not pass
validation or does not have a validator assigned.

Metadata validators are modular and can be added to the service via configuration without
changing the service core code. Multiple validators can be assigned to each metadata key.

Sample metadata has the following structure (also see the service spec file):

```
{"metadata_key_1: {"metadata_value_key_1_1": "metadata_value_1_1",
                                        ...
                   "metadata_value_key_1_N": "metadata_value_1_N",
                   },
                      ...
 "metadata_key_N: {"metadata_value_key_N_1": "metadata_value_N_1",
                                        ...
                   "metadata_value_key_N_N": "metadata_value_N_N",
                   }
}
```
Metadata values are primitives: a string, float, integer, or boolean.

A simple example:
```
{"temperature": {"measurement": 1.0,
                 "units": "Kelvin"
                 },
 "location": {"name": "Castle Geyser",
              "lat": 44.463816,
              "long": -110.836471
              }
}
```

In this case, a validator would need to be assigned to the `temperature` and `location`
metadata keys. Validators are `python` callables that accept the key and the value of the key as
callable parameters. E.g. in the case of the `temperature` key, the arguments to the function
would be:

```
("temperature", {"measurement": 1.0, "units": "Kelvin"})
```

If the metadata is incorrect, the validator should return an error message as a string. Otherwise
it should return `None` unless the validator cannot validate the metadata due to some
uncontrollable error (e.g. it can't connect to an external server after a reasonable timeout),
in which case it should throw an exception.

 Validators are built by a builder function specified in the configuration (see below).
 The builder is passed any parameters specified in the configuration as a
 mapping. This allows the builder function to set up any necessary state for the validator
 before returning the validator for use. Examine the validators in
`SampleService.core.validator.builtin` for examples. A very simple example might be:

 ```python
 def enum_builder(params: Dict[str, str]
        ) -> Callable[[str, Dict[str, Union[float, int, bool, str]]], Optional[str]]:
    # should handle errors better here
    enums = set(params['enums'])
    valuekey = params['key']

    def validate_enum(key: str, value: Dict[str, Union[float, int, bool, str]]) -> Optional[str]:
        # key parameter not needed in this case
        if value.get(valuekey) not in enums:
            return f'Illegal value for key {valuekey}: {value.get(valuekey)}'
        return None

    return validate_enum
```

### Prefix validators

The sample service supports a special class of validators that will validate any keys that match
a specified prefix, as opposed to standard validators that only validate keys that match exactly.
Otherwise they behave similarly to standard validators except the validator function signature is:

```
(prefix, key, value)
```

For the temperature example above, if the prefix for the validator was `temp`, the arguments
would be

```
("temp", "temperature", {"measurement": 1.0, "units": "Kelvin"})
```

A particular metadata key can match one standard validator key (which may have many 
validators associated with it) and up to `n` prefix validator keys, where `n` is the length of the
key in characters. Like standard metadata keys, prefix validator keys may have multiple
validators associated with them. The validators are run in the order of the list for a particular
prefix key, but the order the matching prefix keys are run against the metadata key is not
specified.

A toy example of a prefix validators builder function might be:

```python
def chemical_species_builder(params: Dict[str, str]
        ) -> Callable[[Dict[str, str, Union[float, int, bool, str]]], Optional[str]]:
    # or contact an external db or whatever
    chem_db = setup_sqlite_db_wrapper(params['sqlite_file'])
    valuekey = params['key']

    def validate_cs(prefix: str, key: str, value: Dict[str, Union[float, int, bool, str]]
            ) -> Optional[str]:
        species = key[len(prefix):]
        if value[valuekey] != species:
            return f'Species in key {species} does not match species in value {value[valuekey]}'
        if not chem_db.find_chem_species(species):
            return f'No such chemical species: {species}
        return None

    return validate_cs
```

### Source metadata

In some cases, metadata at the data source may be transformed prior to ingest into the
Sample Service - for instance, two samples from different sources may be associated with
metadata items that are semantically equivalent but have different names and are represented in
different units. Prior to storage in the Sample Service, those items may be transformed to use
the same metadata key and representation for the value.

The Sample Service allows storing these source keys and values along with the controlled
metadata such that the original metadata may be reconstructed. The data is not validated other
than basic size checks and is stored on an informational basis only.

See the API specification for more details.

## Static key metadata

A service administrator can define metadata associated with the metadata keys - e.g. metadata
*about* the keys. This might include a text definition, semantic information about the key,
an ontology ID if the key represents a particular node in an ontology, etc. This metadata is
defined in the validator configuration file (see below) and is accessible via the service API.

## Configuration

The `deploy.cfg` configuration file contains a key, `metadata-validator-config-repo`, that if
provided must be a relative github path that points to a validator configuration github repo. 
Setting `github-token` will help to avoid any rate limiting that may occur (1k/hr vs 60/hr requests.)
The configuration repo should have chronological releases containing a configuration file. This file's 
name can be specified with `metadata-validator-config-filename` (`metadata_validation.yml` by default). 
The most recent release from the specified repo will be loaded. If preleases should also be included, 
set the `metadata-validator-config-prerelease` config variable to 'true'. A direct file URL overide can 
also be provided with the `metadata-validator-config-url` key. The configuration file is loaded on 
service startup and used to configure the metadata validators. If changes are made to the configuration
file the service must be restarted to reconfigure the validators.

The configuration file uses the YAML format and is validated against the following JSONSchema:

```
{
    'type': 'object',
    'definitions': {
        'validator_set': {
            'type': 'object',
            # validate values only
            'additionalProperties': {
                'type': 'object',
                'properties': {
                    'key_metadata': {
                        'type': 'object',
                        'additionalProperties': {
                            'type': ['number', 'boolean', 'string', 'null']
                        }
                    },
                    'validators': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'module': {'type': 'string'},
                                'callable_builder': {'type': 'string'},
                                'parameters': {'type': 'object'}
                            },
                            'additionalProperties': False,
                            'required': ['module', 'callable_builder']
                        }

                    }
                },
                'required': ['validators']
            }
        },
        'additionalProperties': False,
    },
    'properties': {
        'validators': {'$ref': '#/definitions/validator_set'},
        'prefix_validators': {'$ref': '#/definitions/validator_set'},
    },
    'additionalProperties': False
}
```

The configuration consists of a mapping of standard and prefix metadata keys to a further mapping
of metadata key properties, including the list of validator specifications and static metadata
about the key. Each validator is run against the metadata value in order. The `module` key is
a python import path for the module containing a builder function for the validator, while the
`callable_builder` key is the name of the function within the module that can be called to 
create the validator. `parameters` contains a mapping that is passed directly to the
callable builder. The builder is expected to return a callable with the call signature as
described previously.

A simple configuration might look like:
```
validators:
    foo:
        validators:
            - module: SampleService.core.validator.builtin
              callable_builder: noop
        key_metadata:
            description: test key
            semantics: none really
    stringlen:
        validators:
            - module: SampleService.core.validator.builtin
              callable_builder: string
              parameters:
                  max-len: 5
            - module: SampleService.core.validator.builtin
              callable_builder: string
              parameters:
                  keys: spcky
                  max-len: 2
        key_metadata:
            description: check that no strings are longer than 5 characters and spcky is <2
prefix_validators:
    gene_ontology_:
        validators:
            - module: geneontology.plugins.kbase
              callable_builder: go_builder
              parameters: 
                  url: https://fake.go.service.org/api/go
                  apitoken: abcdefg-hijklmnop
        key_metadata:
            description: The key value contains a GO ontology ID that is linked to the sample.
            go_url: https://fake.go.service.org/api/go
            date_added_to_service: 2020/3/8
```

In this case any value for the `foo` key is allowed, as the `noop` validator is assigned to the
key. Note that if no validator was assigned to `foo`, including that key in the metadata would
cause a validation error.
The `stringlen` key has two validators assigned and any metadata under that key must pass
both validators. The first validator ensures that no keys or value strings in in the metadata map
are longer than 5 characters, and the second ensures that the value of the `spcky` key is a
string of no more than two characters. See the documentation for the `string` validator (below)
for more information.
Finally, the wholly fabricated `gene_ontology_` prefix validator will match **any** key
starting with `gene_ontology_`. The validator code might look up the suffix of the key,
say `GO_0099593`, at the provided url to ensure the suffix matches a legitmate ontology
term. Without a prefix validator, a validator would have to be written for each individual
ontology term, which is infeasible.

All the metadata keys have static metadata describing the semantics of the keys and other
properties that service users might need to properly use the keys.

## Built in validators

All built in validators are in the `SampleService.core.validator.builtin` module.

### noop

Example configuration:
```
validators:
    metadatakey:
        validators:
            - module: SampleService.core.validator.builtin
              callable_builder: noop
```

This validator accepts any and all values.

### string

Example configuration:
```
validators:
    metadatakey:
        validators:
            - module: SampleService.core.validator.builtin
              callable_builder: string
              parameters:
                  keys: ['key1', 'key2']
                  required: True
                  max-len: 10
```

* `keys` is either a string or a list of strings and determines which keys will be checked by the
  validator. If the key exists, its value must be a string or `None` (`null` in JSON-speak).
* `required` requires any keys in the `keys` field to exist in the map, although their value may
  still be `None`.
* `max-len` determines the maximum length in characters of the values of the keys listed in `keys`.
  If `keys` is not supplied, then it determines the maximum length of all keys and string values
  in the metadata value map.

### enum

Example configuration:
```
validators:
    metadatakey:
        validators:
            - module: SampleService.core.validator.builtin
              callable_builder: enum
              parameters:
                  keys: ['key1', 'key2']
                  allowed-values: ['red', 'blue', 'green]
```

* `allowed-values` is a list of primitives - strings, integers, floats, or booleans - that are
  allowed metadata values. If `keys` is not supplied, all values in the metadata value mapping must
  be one of the allowed values.
* `keys` is either a string or a list of strings and determines which keys will be checked by the
  validator. The key must exist and its value must be one of the `allowed-values`.

### units

Example configuration:
```
validators:
    metadatakey:
        validators:
            - module: SampleService.core.validator.builtin
              callable_builder: units
              parameters:
                  key: 'units'
                  units: 'mg/L'
```

* `key` is the metadata value key that will be checked against the `units` specification.
* `units` is a **unit specification in the form of an example**. Any units that can be converted
  to the given units will be accepted. For example, if `units` is `K`, then `degF`, `degC`, and
  `degR` are all acceptable input to the validator. Similarly, if `N` is given, `kg * m / s^2` and
  `lb * f / s^2` are both acceptable.

### number

Example configuration:
```
validators:
    metadatakey:
        validators:
            - module: SampleService.core.validator.builtin
              callable_builder: number
              parameters:
                  keys: ['length', 'width']
                  type: int
                  required: True
                  gte: 42
                  lt: 77
```

Ensures all values are integers or floats.

* `keys`, which is either a string or a list of strings, determines which keys in the metdata value
  map are checked. If omitted, all keys are checked.
* If `required` is specified, the keys in the `keys` list must exist in the metadata value map,
  although their value may be `null`.
* `type` specifies that the number or numbers must be integers if set to `int` or any number if
  omitted or set to `float` or `null`.
* `gt`, `gte`, `lt`, and `lte` are respectively greater than, greater than or equal,
  less than, and less than or equal, and specify a range in which the number or numbers must exist.
  If `gt` or `lt` are specified, `gte` or `lte` cannot be specified, respectively, and vice versa.

### ontology_has_ancestor

Example configuration:
```
validators:
    metadatakey:
        validators:
            - module: SampleService.core.validator.builtin
              callable-builder: ontology_has_ancestor
              parameters:
                  ontology: 'envo_ontology'
                  ancestor_term: 'ENVO:00010483'
                  srv_wiz_url: 'https://kbase.us/services/service_wizard'
```

* `ontology` is the ontology that the meta value will be checked against.
* `ancestor_term` is the ancestor ontology term that will be used to check whether meta value has such ancestor or not.   
* `srv_wiz_url` is the kbase service wizard url for getting OntologyAPI service.
