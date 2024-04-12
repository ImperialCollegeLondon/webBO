import models as model
from sqlalchemy import MetaData
from sqlalchemy.orm import class_mapper
from sqlalchemy_schemadisplay import create_uml_graph

# lets find all the mappers in our model
mappers = []
for attr in dir(model):
    if attr[0] == "_":
        continue
    try:
        cls = getattr(model, attr)
        mappers.append(class_mapper(cls))
    except:
        pass

# pass them to the function and set some formatting options
graph = create_uml_graph(
    mappers,
    show_operations=False,  # not necessary in this case
    show_multiplicity_one=False,  # some people like to see the ones, some don't
)
graph.write_png("schema.png")  # write out the file
