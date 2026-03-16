import datetime
import json
import os
import sys

import pysmartdatamodels
import pytz
from rdflib import Graph, URIRef

import graph_util


def write_notes(g: Graph, dataModel, outDir: str):
    n = ['notesPrevious:',
         '',
         'notesEnd:']  # TODO
    dirName = outDir + '/dataModel.' + dataModel
    try:
        os.mkdir(dirName)
    except FileExistsError:
        pass
    with open(dirName + '/notes.yaml', "w") as outfile:  # notes
        for l in n:
            outfile.write(l + '\n')
    return


def write_subject_notes(dataModel, root: URIRef, desc: str, outDir: str):
    subject = graph_util.get_last_token(root)
    n = ['notesHeader:',
         '  ' + desc,
         'notesMiddle:',
         '',
         'notesFooter:',
         '',
         'notesReadme:',
         '  ' + desc,
         ]
    dirName = outDir + '/dataModel.' + dataModel + '/' + subject
    try:
        os.mkdir(dirName)
    except:
        pass
    with open(dirName + '/notes.yaml', 'w') as outfile:  # notes
        for l in n:
            outfile.write(l + '\n')
    return


def ngsi_ld_example_generator_str(schema: str, dataModel: str, subject: str):
    """It returns a fake normalized ngsi-ld format example based on the given json schema
    Parameters:
        schema: schema.json contents
        dataModel: repo name
        subject: model name

    Returns:
        if the input parameter exists and the json schema is a valide json:
            a fake normalized ngsi-ld format example stored in dictionary format
        if there's any problem related to input parameter and json schema:
            False
    """

    if dataModel == "" or subject == "":
        return False

    output = {}
    tz = pytz.timezone("Europe/Madrid")

    try:
        payload = json.loads(schema)
    except ValueError:
        output["result"] = False
        output["cause"] = "Schema parameter value is not a valid json"
        output["time"] = str(datetime.datetime.now(tz=tz))
        # output["parameters"] = {"schema_url: ": schema_url}
        print(json.dumps(output))
        sys.exit()

    if payload == "":
        return False

    fullDict = {}
    fullDict['id'] = {}
    if "allOf" in payload:
        for index in range(len(payload["allOf"])):
            if "properties" in payload["allOf"][index]:
                fullDict = {**fullDict, **payload["allOf"][index]["properties"]}
            else:
                fullDict = {**fullDict, **payload["allOf"][index]}
    elif "anyOf" in payload:
        for index in range(len(payload["anyOf"])):
            if "properties" in payload["anyOf"][index]:
                fullDict = {**fullDict, **payload["anyOf"][index]["properties"]}
            else:
                fullDict = {**fullDict, **payload["anyOf"][index]}
    elif "oneOf" in payload:
        for index in range(len(payload["oneOf"])):
            if "properties" in payload["oneOf"][index]:
                fullDict = {**fullDict, **payload["oneOf"][index]["properties"]}
            else:
                fullDict = {**fullDict, **payload["oneOf"][index]}
    else:
        fullDict = payload["properties"].copy()

    for prop in fullDict:
        parsedProperty = pysmartdatamodels.parse_property({prop: fullDict[prop]}, dataModel, 0)
        if prop in ["id"]:
            output = {**output, **parsedProperty}
        elif prop in ["type"]:
            output = {**output, **{prop: parsedProperty}}
        else:
            output = {**output, **{prop: parsedProperty}}
    output["@context"] = [pysmartdatamodels.create_context('dataModel.' + dataModel)]

    return output


def write_ngsi_ld_examples(schema: str, dataModel: str, subject: str, outDir: str):

    output = ngsi_ld_example_generator_str(schema, dataModel, subject)

    en = json.dumps(output, indent=4)
    with open(outDir + '/dataModel.' + dataModel + '/' + subject + '/example-normalized.jsonld', 'w') as outfile:
        r = outfile.write(en)

    keyvalues = pysmartdatamodels.normalized2keyvalues(output)
    en = json.dumps(keyvalues, indent=4)
    with open(outDir + '/dataModel.' + dataModel + '/' + subject + '/example.jsonld', 'w') as outfile:
        r = outfile.write(en)

    return r
