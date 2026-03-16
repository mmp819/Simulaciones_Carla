# rdf2sdm - RDF to Smart Data Models Conversion

Converts ontologies in RDF format (turtle etc.) to files necessary to publish a data model in the Smart Data Models repository as per the [instructions](https://smartdatamodels.org/index.php/5-files-for-creating-a-new-data-model/).

Two examples demonstrate the usage: `test_actuator.py` and `test_ACDSi.py`. Their respective source ontologies can be downloaded from [SAREF4BLDG](https://saref.etsi.org/saref4bldg/) and [ACDSi](https://github.com/fdrobnic/ontologies/blob/main/ACDSi.ttl).

Generated output files are saved into two subfolders under the `sdm/dataModel.*` folder:
* `<upper class name>` - model files
* `master` - common `context.jsonld` file, which must be served from the URL to which the `example*.jsonld` refer in their `@context` list

## Testing

The generated files can be tested using a local test setup as presented in the `docker` subfolder.

## More info

The software complements the article:

Automatic Generation of NGSI-LD Data Models from RDF Ontologies: Developmental Studies of Children and Adolescents Use Case by Franc Drobnič, Gregor Starc, Gregor Jurak, Andrej Kos, and Matevž Pustišek [(DOI)](https://doi.org/10.3390/app16020992)

© 2025. This work is openly licensed via [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).



