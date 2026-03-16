from rdf2sdm import *

baseUri = 'https://saref.etsi.org/saref4bldg/'
dataModel = 'S4BLDG'
classes = ['https://saref.etsi.org/saref4bldg/Actuator']
outDir = './sdm'

rt = Rdf2sdm("saref4bldg.ttl", baseUri)

def sort_tuple(value: tuple):
    try:
        return str(value[0]) + ' ' + str(value[1]) + ' ' + str(value[2])
    except TypeError:
        pass


t = [a for a in rt.g.triples((None, None, None))]
t.sort(key=sort_tuple)
with open("triples_all.json", "w") as outfile:
    outfile.write(json.dumps(t, indent=4))

additional = {
    rdflib.term.URIRef('https://saref.etsi.org/core/Measurement'): 'https://raw.githubusercontent.com/smart-data-models/dataModel.S4BLDG/master/S4BLDG-schema.json#/definitions/Measurement'
}

for objectRoot in classes:  # graph_util.get_classes(rt.g):
    r = rt.translate(data_model=dataModel, rootUri=objectRoot, additional=additional)
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
