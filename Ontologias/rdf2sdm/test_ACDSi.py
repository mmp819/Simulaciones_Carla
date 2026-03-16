from rdf2sdm import *

baseUri = 'https://github.com/fdrobnic/ontologies/ACDSi'
dataModel = 'ACDSi'
# objectRoot = 'https://github.com/fdrobnic/ontologies/ACDSi#EUROfit'
# objectRoot = 'https://github.com/fdrobnic/ontologies/ACDSi#SLOfit'
objectRoot = 'https://github.com/fdrobnic/ontologies/ACDSi#ACDSiMeasurement'
outDir = './sdm'

rt = Rdf2sdm("../artos/ACDSi.ttl", baseUri)

r = rt.translate(data_model=dataModel, rootUri=objectRoot)
if not r:
    print('Error transforming RDF ' + r.__repr__())
    exit(r)

rt.write_model_notes(outDir=outDir)

rt.write_subject_notes(outDir=outDir)

rt.write_notes_context(outDir=outDir)

r = rt.write_schema(outDir=outDir)
if not r:
    print('Error writing schema ' + r.__repr__())
    exit(r)

r = rt.write_context(outDir=outDir)
if not r:
    print('Error writing context ' + r.__repr__())
    exit(r)

y = rt.write_model_yaml(outDir=outDir)
if not y:
    print('Error writing model.yaml ' + y.__repr__())
    exit(y)

e = rt.write_ngsi_ld_example(outDir=outDir)
if not e:
    print('Error writing example ' + e.__repr__())
    exit(e)

print('Success')
