from rdf2sdm import *

baseUri = 'http://www.w3.org/ns/sosa/'
dataModel = 'SOSA'
outDir = './sddm-conversion'

rel_type = "https://smart-data-models.github.io/data-models/common-schema.json#/definitions/EntityIdentifierType"
additional_mappings = {
    URIRef("http://www.w3.org/ns/sosa/Sensor"): rel_type,
    URIRef("http://www.w3.org/ns/sosa/Platform"): rel_type,
    URIRef("http://www.w3.org/ns/sosa/Observation"): rel_type,
    URIRef("http://www.w3.org/ns/sosa/Result"): rel_type,
    URIRef("http://www.w3.org/ns/sosa/FeatureOfInterest"): rel_type,
    URIRef("http://www.w3.org/ns/sosa/Procedure"): rel_type,
    URIRef("http://www.w3.org/ns/sosa/ObservableProperty"): rel_type
}

clases_a_procesar = ['Platform', 'Sensor', 'Observation']

if not os.path.exists(outDir):
    os.makedirs(outDir)

for clase in clases_a_procesar:
    print(f"--- Procesando entidad: {clase} ---")
    objectRoot = f'http://www.w3.org/ns/sosa/{clase}'
    rt = Rdf2sdm("../sosa.ttl", baseUri)

    r = rt.translate(data_model=dataModel, rootUri=objectRoot, additional=additional_mappings)

    if not r:
        print('Error transforming RDF ' + r.__repr__())
        continue

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
