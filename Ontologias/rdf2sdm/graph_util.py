from rdflib import Graph, RDF, RDFS, OWL, XSD, URIRef


def get_root(gr: Graph):
    a = []
    for s, p, o in gr:
        if p == RDF.type and o == OWL.Class:
            if isinstance(s, type([])) or isinstance(s, type(())):
                su = s[0]
            else:
                su = s
            anc = [a[2] for a in gr.triples((su, RDFS.subClassOf, None))]
            if len(anc) == 0:
                a.append(su)
    return a


def get_classes(gr: Graph):
    a = []
    for s, p, o in gr:
        if p == RDF.type and o == OWL.Class:
            if isinstance(s, type([])) or isinstance(s, type(())):
                su = s[0]
            else:
                su = s
            a.append(su)
    return a


def get_leaves(gr: Graph):
    a = []
    for s, p, o in gr:
        if p == RDF.type and o == OWL.Class:
            if isinstance(s, type([])) or isinstance(s, type(())):
                su = s[0]
            else:
                su = s
            anc = [a[0] for a in gr.triples((None, RDFS.subClassOf, su))]
            if len(anc) == 0:
                a.append(su)
    return a


def get_subtree(gr: Graph, root):
    t = []
    for n in [a[0] for a in gr.triples((None, RDFS.subClassOf, root))]:
        t = t.append(get_subtree(gr, n))
    return t


def get_last_token(objectRoot: str):
    subject = URIRef(objectRoot).fragment
    if subject == '':
        subject = objectRoot.split('/')[-1]

    return subject
