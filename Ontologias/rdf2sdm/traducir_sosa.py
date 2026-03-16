from rdf2sdm import Rdf2sdm
import graph_util
import os

# Configuración
baseUri = 'http://www.w3.org/ns/sosa/'
dataModel = 'SOSA'
rdfFile = '../sosa.ttl'
outDir = './sdm-sosa'

# Asegurar que existe el directorio de salida
if not os.path.exists(outDir):
    os.makedirs(outDir)

# 1. Cargar la ontología
rt = Rdf2sdm(rdfFile, baseUri)

# 2. Obtener todas las clases (OWL.Class) automáticamente
# La función get_classes busca los sujetos que son tipo OWL.Class
all_classes = graph_util.get_classes(rt.g)

print(f"Se han detectado {len(all_classes)} clases en el fichero.")

# 3. Iterar y traducir cada una
for class_uri in all_classes:
    uri_str = str(class_uri)
    
    # Solo procesamos lo que pertenece a SOSA para evitar basura de importaciones
    if uri_str.startswith(baseUri):
        subject = graph_util.get_last_token(uri_str) # Extrae el nombre final, ej: 'Sensor'
        print(f"Traduciendo clase: {subject}...")

        # Traducir la lógica de la clase al formato Smart Data Model
        success = rt.translate(data_model=dataModel, rootUri=uri_str)
        
        if success:
            # Escribir todas las piezas del modelo
            rt.write_model_notes(outDir=outDir)     # Notas globales del modelo
            rt.write_subject_notes(outDir=outDir)   # Descripción específica de la clase
            rt.write_notes_context(outDir=outDir)   # Mapeo de términos
            rt.write_schema(outDir=outDir)          # El archivo JSON Schema principal
            rt.write_context(outDir=outDir)         # Contexto JSON-LD
            rt.write_model_yaml(outDir=outDir)      # Versión YAML para documentación
            rt.write_ngsi_ld_example(outDir=outDir) # Genera ejemplos normalized y keyvalues
        else:
            print(f"Error al procesar la clase: {subject}")

print("\n¡Traducción completada con éxito!")