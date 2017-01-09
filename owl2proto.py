#!/usr/bin/env python

import sys
import rdflib
import jinja2
import logging
import textwrap
from rdflib.namespace import RDF, RDFS, OWL

MESSAGE_TEMPLATE = """
{% if comment %}
/*
{{comment}}
*/
{%- endif %}
message {{name}} {
{%- for field in fields %}
    {{fields[field]}} {{field}} = {{loop.index}};
{%- endfor %}
{%- for edge in edges %}
    repeated string {{edge}} = {{loop.index + fields|length}};
{%- endfor %}
}
"""

class ProtoMessage:
    def __init__(self, name):
        self.name = name
        self.fields = {}
        self.edges = []
        self.comment = None
    
    def add_field(self, name, vrange):
        if vrange is None:
            vrange = "string"
        self.fields[name] = vrange
    
    def add_edge_type(self, name):
        self.edges.append(name)
    
    def add_comment(self, comment):
        self.comment = "\n".join(textwrap.wrap(comment.encode('ascii', 'ignore')))
    
    def add_superclass(self, superclass):
        changed = False
        for f,t in superclass.fields.items():
            if f not in self.fields:
                self.fields[f] = t
                changed = True
        return changed
        
    
    def __str__(self):
        return jinja2.Template(MESSAGE_TEMPLATE).render(name=self.name, fields=self.fields, edges=self.edges, comment=self.comment)

def url_trim(url):
    return url.split("#")[1]

message_map = {}

QPREFIX="http://www.biopax.org/release/biopax-level3.owl#"

g = rdflib.Graph()
result = g.parse(sys.argv[1])

#Find all of the different classes
for subj, pred, obj in g.triples((None, RDF.type, OWL.Class)):
    if subj.startswith(QPREFIX):
        n = url_trim(subj)
        message_map[n] = ProtoMessage(n)
        for class_subj, class_pred, class_obj in g.triples( (subj, None, None) ):
            if class_pred == RDFS.comment:
                #print "\t", class_pred, class_obj
                message_map[n].add_comment(class_obj)

#Find the different properties for each of the classes
for subj, pred, obj in g.triples((None, RDF.type, OWL.ObjectProperty)):
    if subj.startswith(QPREFIX):
        odomain = None
        orange = None
        for prop_subj, prop_pred, prop_obj in g.triples((subj, RDFS.domain, None)):
            if prop_obj.startswith(QPREFIX):
                odomain = url_trim(prop_obj)
        for prop_subj, prop_pred, prop_obj in g.triples((subj, RDFS.range, None)):
            if prop_obj.startswith(QPREFIX):
                orange = url_trim(prop_obj)

        if odomain is not None:
            message_map[odomain].add_field( url_trim(subj), orange )

#Find subclasses
subclasses = []
for subj, pred, obj in g.triples((None, RDFS.subClassOf, None)):
    if subj.startswith(QPREFIX) and obj.startswith(QPREFIX):
        #print subj, pred, obj
        n = url_trim(subj)
        m = url_trim(obj)
        if n in message_map and message_map[m]:
            subclasses.append( (n,m) )
found = True
while found:
    found = False
    for a, b in subclasses:
        if message_map[a].add_superclass(message_map[b]):
            found = True
    
"""
for subj, pred, obj in g.triples((None, RDF.type, OWL.FunctionalProperty)):
    for prop_subj, prop_pred, prop_obj in g.triples((subj, RDFS.domain, None)):
        domain = None
        for prop_subj, prop_pred, prop_obj in g.triples((subj, RDFS.domain, None)):
            if prop_obj.startswith("http://www.biopax.org/release/biopax-level3.owl#"):
                domain = url_trim(prop_obj)
            #print prop_subj, prop_pred, prop_obj
        if domain is not None:
            message_map[domain].add_edge_type( url_trim(subj) )
"""

out = sys.stdout
out.write('syntax = "proto3";\n')
out.write("package biopax;\n\n")
for m in message_map.values():
    out.write("%s\n" % m)
