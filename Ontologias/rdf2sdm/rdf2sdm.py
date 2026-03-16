import json
import os

import rdflib.paths
import yaml
from rdflib import Graph, URIRef, Literal, RDF, RDFS, DCTERMS, OWL, XSD

import out_util
import graph_util


class Rdf2sdm:
    g: Graph
    globalDesc: str
    baseUri: str
    dataModel: str = ''
    objectRoot: URIRef  # class IRI for which the output is to be written
    subject: str  # class name (last fragment from IRI) for which the output is to be written
    properties: dict
    anonAncProperties: dict
    schema_obj: dict
    propertyAttrs: dict
    imp: dict  # imported graphs

    def __init__(self, rdfFile: str = '', baseUri: str = ''):
        """

        Args:
            rdfFile: path to RDF file
            baseUri: base URI
        """
        self.g = Graph()
        self.baseUri = baseUri

        if rdfFile != '':
            result = self.g.parse(source=rdfFile)

            t = list(self.g.triples((URIRef(self.baseUri), RDFS.label, None)))
            if len(t) == 0:
                t = list(self.g.triples((URIRef(self.baseUri), DCTERMS.description, None)))

            if isinstance(t[0][2], Literal):
                self.globalDesc = t[0][2].value
            else:
                self.globalDesc = t[0][2]
        self.properties = dict()
        self.anonAncProperties = dict()
        self.imp = dict()

    def translate(self, data_model: str, rootUri: str, additional: dict = {}, findAnonAncProp: bool = True) -> int:
        """

        Args:
            data_model: repository name
            rootUri: class IRI to parse
            additional: dict containing additional translations

        Returns:
            status: int

        """
        self.objectRoot = URIRef(rootUri)
        self.dataModel = data_model
        self.subject = graph_util.get_last_token(self.objectRoot)
        dl = list(self.g.triples((self.objectRoot, RDFS.comment, None)))
        if len(dl) > 0:
            desc = dl[0][2]
        else:
            desc = ''
        if isinstance(desc, Literal):
            desc = desc.value
        self.schema_obj = {
            "$schema": "http://json-schema.org/schema#",
            "$schemaVersion": "0.0.1",
            "$id": 'https://smart-data-models.github.com/dataModel.' + self.dataModel + '/' + self.subject + '/schema.json',
            "title": "Smart data models - " + self.subject + ' schema',
            "modelTags": self.dataModel + ' ' + self.subject,
            "description": desc,
            "type": "object",
            "derivedFrom": self.baseUri,
            "license": "https://opensource.org/licenses/BSD-3-Clause",  # TODO CCBY 4 ?
            "allOf": [
                {
                    "$ref": "https://smart-data-models.github.io/data-models/common-schema.json#/definitions/GSMA-Commons"
                },
                {
                    "$ref": "https://smart-data-models.github.io/data-models/common-schema.json#/definitions/Location-Commons"
                }
            ]
        }

        self.properties = dict()
        self.anonAncProperties = dict()
        self.propertyAttrs = dict()
        cl = list(rdflib.paths.eval_path(self.g, (None, RDFS.subClassOf * rdflib.paths.OneOrMore, self.objectRoot)))
        if len(cl) == 0:
            cl = [(self.objectRoot, None)]
        for r in cl:
            for l in self.g.triples((r[0], RDFS.subClassOf, None)):
                pr = list(self.g.triples((l[2], OWL.onProperty, None)))
                if len(pr) == 0:
                    continue
                k = graph_util.get_last_token(pr[0][2])
                dts = list(self.g.triples((l[2], (OWL.allValuesFrom | OWL.someValuesFrom), None)))
                if len(dts) == 0:
                    dts = list(self.g.triples((pr[0][2], RDFS.range, None)))
                if len(dts) == 0:
                    continue
                fmt = ''
                r = ''
                if dts[0][2] in [XSD.decimal, XSD.numeric, XSD.int, XSD.integer, XSD.float, XSD.double]:
                    dt = 'number'
                    mdl = 'https://schema.org/Number'
                elif dts[0][2] == XSD.string:
                    dt = 'string'
                    mdl = 'https://schema.org/Text'
                elif dts[0][2] in [XSD.date, XSD.dateTime, XSD.dateTimeStamp]:
                    dt = 'string'
                    mdl = 'https://schema.org/Text'
                    if dts[0][2] == XSD.date:
                        fmt = 'date'
                    elif dts[0][2] in [XSD.dateTime, XSD.dateTimeStamp]:
                        fmt = 'date-time'
                elif dts[0][2] == XSD.boolean:
                    dt = 'boolean'
                    mdl = 'https://schema.org/Boolean'
                else:
                    if dts[0][2] in additional.keys():
                        r = additional[dts[0][2]]
                    #else:
                    #    if dts[0][2] not in self.imp.keys():
                    #        self.imp[dts[0][2]] = Graph()
                    #        self.imp[dts[0][2]].parse(location=dts[0][2])
                    dt = ''
                    mdl = ''
                d = ''
                for a in self.g.triples((pr[0][2], RDFS.comment, None)):
                    if isinstance(a[2], Literal):
                        d = a[2].value
                    else:
                        d = a[2]
                if r != '':
                    v = {
                        '$ref': r,
                        'description': "Property. " + d
                    }
                else:
                    v = {
                        'type': dt,
                        # 'minimum': 0,  # TODO
                        'description': "Property. Model: '" + mdl + "'. " + d
                    }
                if fmt != '':
                    v['format'] = fmt
                if k != '' and v != {}:
                    self.properties[k] = v
                    self.propertyAttrs[k] = {'description': d, 'model': mdl, 'iri': pr[0][2].__str__()}

        lrt = Rdf2sdm()
        cl = list(rdflib.paths.eval_path(self.g, (self.objectRoot, RDFS.subClassOf * rdflib.paths.OneOrMore, None)))
        for r in cl:
            for l in self.g.triples((r[1], RDFS.subClassOf, None)):
                pr = list(self.g.triples((l[2], OWL.onProperty | OWL.maxCardinality, None)))
                if len(pr) > 0:
                    k = graph_util.get_last_token(pr[0][2])
                    ol = list(rdflib.paths.eval_path(self.g, (pr[0][0], (OWL.allValuesFrom | OWL.unionOf | RDF.first | RDF.rest | OWL.maxCardinality) * rdflib.paths.OneOrMore, None)))
                    for o in ol:
                        if isinstance(o[1], URIRef) and o[1] != RDF.nil and findAnonAncProp:
                            k2 = o[1].split('/')[-1]
                            do = list(rdflib.paths.eval_path(self.g, (o[1], RDFS.comment * rdflib.paths.OneOrMore, None)))
                            if isinstance(do[0][1], Literal):
                                dv = do[0][1].value
                            else:
                                dv = do[0][1]
                            d = 'Relationship. ' + dv + ' (' + k2 + ')'
                            v = {
                                "$ref": "https://smart-data-models.github.io/data-models/common-schema.json#/definitions/EntityIdentifierType",
                                "description": d
                            }
                            if k != '' and v != {}:
                                self.anonAncProperties[k + k2] = v
                                self.propertyAttrs[k + k2] = {'description': d, 'model': '', 'iri': o[1].__str__()}

                        elif isinstance(o[1], Literal):
                            dtp = list(rdflib.paths.eval_path(self.g, (pr[0][2], RDF.type, OWL.DatatypeProperty)))
                            if len(dtp) > 0:
                                do = list(rdflib.paths.eval_path(self.g, (pr[0][2], RDFS.comment * rdflib.paths.OneOrMore, None)))
                                if isinstance(do[0][1], Literal):
                                    d = do[0][1].value
                                else:
                                    d = do[0][1]
                                mdl = 'https://schema.org/Text'
                                v = {
                                    "type": "string",
                                    "description": 'Property. ' + d
                                }
                                if k != '' and v != {}:
                                    self.anonAncProperties[k] = v
                                    self.propertyAttrs[k] = {'description': d, 'model': mdl, 'iri': pr[0][2].__str__()}

            defs = list(rdflib.paths.eval_path(self.g, (r[1], RDFS.isDefinedBy * rdflib.paths.OneOrMore, None)))
            for df in defs:
                if df[1] not in self.imp.keys():
                    self.imp[df[1]] = Graph()
                    self.imp[df[1]].parse(location=df[1])
                lrt = Rdf2sdm(df[1], r[1])
                res = lrt.translate(data_model='A', rootUri=r[1], additional=additional, findAnonAncProp=False)
                if not res:
                    return res

        lp = {
            "type": {
                "type": "string",
                "description": "Property. NGSI entity type. It must be equal to `" + self.subject + "`",
                "enum": [
                    self.subject
                ]
            }
        }
        lp.update(self.properties)
        lp.update(self.anonAncProperties)
        if len(lrt.anonAncProperties) > 0:
            lp.update(lrt.anonAncProperties)
        self.schema_obj['allOf'].append({'properties': lp})

        self.schema_obj['required'] = [
            "id",
            "type"
        ]

        return 1

    def write_model_notes(self, outDir: str) -> None:
        """
        Writes the model notes.

        Args:
            outDir: output directory
        """
        if len(self.properties) > 0 or len(self.anonAncProperties) > 0:
            out_util.write_notes(self.g, dataModel=self.dataModel, outDir=outDir)

    def write_subject_notes(self, outDir: str):
        """
        Writes the subject notes.

        Args:
            outDir: output directory
        """
        if len(self.properties) > 0 or len(self.anonAncProperties) > 0:
            out_util.write_subject_notes(dataModel=self.dataModel, root=self.objectRoot, desc=self.globalDesc, outDir=outDir)

    def write_notes_context(self, outDir: str):
        """

        Args:
            outDir: output directory
        """
        if not isinstance(self.schema_obj, dict):
            return False

        if len(self.properties) > 0 or len(self.anonAncProperties) > 0:
            prop = {}
            for a in self.schema_obj['allOf']:
                if 'properties' in a.keys():
                    prop = a['properties']
                    break
            # @context:
            dirName = outDir + '/dataModel.' + self.dataModel
            try:
                os.mkdir(dirName)
            except FileExistsError:
                pass
            context_filename = dirName + '/notes_context.jsonld'
            try:
                with open(context_filename, 'r') as infile:
                    c1 = json.loads(infile.read())['@context']
            except FileNotFoundError:
                c1 = {}
            c = {}
            c[self.subject] = self.objectRoot.__str__()
            for k in prop:
                if k != 'type' and k in self.propertyAttrs.keys():
                    c[k] = self.propertyAttrs[k]['iri']
            for k, v in c.items():
                c1[k] = v
            co = {'@context': c1}

            with open(context_filename, "w") as outfile:
                outfile.write(json.dumps(co, indent=2))

    def write_schema(self, outDir: str):
        """

        Args:
            outDir: output directory

        Returns:

        """
        if not isinstance(self.schema_obj, dict):
            return False

        r = True
        if len(self.properties) > 0 or len(self.anonAncProperties) > 0:
            schema = json.dumps(self.schema_obj, indent=4)
            with open(outDir + '/dataModel.' + self.dataModel + '/' + self.subject + '/schema.json', 'w') as outfile:
                r = outfile.write(schema)

        return r

    def write_context(self, outDir: str):
        """

        Args:
            outDir: output directory

        Returns:

        """
        if not isinstance(self.schema_obj, dict):
            return False

        r = True
        if len(self.properties) > 0 or len(self.anonAncProperties) > 0:
            prop = {}
            for a in self.schema_obj['allOf']:
                if 'properties' in a.keys():
                    prop = a['properties']
                    break
            # @context:
            dirName = outDir + '/dataModel.' + self.dataModel + '/master'
            try:
                os.mkdir(dirName)
            except FileExistsError:
                pass
            context_filename = dirName + '/context.jsonld'
            try:
                with open(context_filename, 'r') as infile:
                    c1 = json.loads(infile.read())['@context']
            except FileNotFoundError:
                c1 = {}
            c = {}
            c[self.subject] = 'https://smartdatamodels.org/dataModel.' + self.dataModel + '/' + self.subject
            for k in prop:
                if k != 'type':
                    c[k] = 'https://smartdatamodels.org/dataModel.' + self.dataModel + '/' + k
            c["id"] = "@id"
            c["type"] = "@type"
            c["ngsi-ld"] = "https://uri.etsi.org/ngsi-ld/"
            for k, v in c.items():
                c1[k] = v
            co = {'@context': c1}

            with open(context_filename, 'w+t') as outfile:
                r = outfile.write(json.dumps(co, indent=4, sort_keys=True))

        return r

    def write_model_yaml(self, outDir: str):
        """

        Args:
            outDir: output directory

        Returns:

        """
        if not isinstance(self.schema_obj, dict):
            return False

        if len(self.properties) > 0 or len(self.anonAncProperties) > 0:
            prop = {}
            for a in self.schema_obj['allOf']:
                if 'properties' in a.keys():
                    prop = a['properties']
                    break
            prop_y = {}
            for k, v in prop.items():
                # yaml:
                v_y = {}
                if 'type' in v.keys(): # TODO: $ref
                    v_y['type'] = v['type']
                    # 'minimum': 0,  # TODO
                    if k == 'type':
                        v_y['description'] = v['description']
                    elif k in self.propertyAttrs.keys():
                        v_y['description'] = self.propertyAttrs[k]['description']
                    if 'enum' in v.keys():
                        v_y['enum'] = v['enum']
                    v_y['x-ngsi'] = {
                        'type': 'Property',
                    }
                    if k != 'type' and k in self.propertyAttrs.keys():
                        v_y['x-ngsi']['model'] = self.propertyAttrs[k]['model']
                    if 'format' in v.keys() and v['format'] != '':
                        v_y['format'] = v['format']
                    prop_y[k] = v_y

            # YAML:
            yn = {
                self.subject: {
                    'description': self.schema_obj['description'],
                    'properties': prop_y,
                    'required': ['id', 'type'],
                    'type': 'object',
                    'x-derived-from': self.baseUri,
                    'x-disclaimer': 'Redistribution and use in source and binary forms, with or without modification, are permitted  provided that the license conditions are met. Copyleft (c) 2022 Contributors to Smart Data Models Program',
                    'x-license-url': 'https://github.com/smart-data-models/dataModel.' + self.dataModel + '/blob/master/' + self.subject + '/LICENSE.md',
                    'x-model-schema': 'https://smart-data-models.github.com/dataModel.' + self.dataModel + '/' + self.subject + '/schema.json',
                    'x-model-tags': self.dataModel + ' ' + self.subject,
                    'x-version': '0.0.1'
                }
            }

            with open(outDir + '/dataModel.' + self.dataModel + '/' + self.subject + '/model.yaml', 'w') as file:
                doc = yaml.dump(data=yn, stream=file, Dumper=yaml.SafeDumper)

        return True

    def write_ngsi_ld_example(self, outDir: str):
        """

        Args:
            outDir: output directory

        Returns:

        """
        e = 1
        if len(self.properties) > 0 or len(self.anonAncProperties) > 0:
            schema = json.dumps(self.schema_obj, indent=4)

            e = out_util.write_ngsi_ld_examples(schema, dataModel=self.dataModel, subject=self.subject, outDir=outDir)

        return e
