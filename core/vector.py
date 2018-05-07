from processing.tools import vector

def createUniqueFieldsList(layer, *fields):

    new_field_list = layer.fields().toList()

    for field in fields:

        unique_name = vector.createUniqueFieldName(field.name(), new_field_list)
        field.setName(unique_name)
        new_field_list.append(field)

    return new_field_list

def resolveField(layer, field_name):

    idx = vector.resolveFieldIndex(layer, field_name)

    if idx >= 0:
        return layer.fields()[idx]
    else:
        raise KeyError('No such field %s in layer %s' % (field_name, layer.name()))