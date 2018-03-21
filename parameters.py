from processing.core.parameters import Parameter

class ParameterTableMultipleField(Parameter):

    DATA_TYPE_NUMBER = 0
    DATA_TYPE_STRING = 1
    DATA_TYPE_ANY = -1

    def __init__(self, name='', description='', parent=None, datatype=-1):
        
        # super(ParameterTableMultipleField, self).__init__(name, description)
        Parameter.__init__(self, name, description)

        self.parent = parent
        self.value = []
        self.datatype = datatype

    def __str__(self):
        return self.name + ' <' + self.__module__.split('.')[-1] + ' from ' \
            + self.parent + '>'

    def dataType(self):
        if self.datatype == self.DATA_TYPE_NUMBER:
            return 'numeric'
        elif self.datatype == self.DATA_TYPE_STRING:
            return 'string'
        else:
            return 'any'

    def getValueAsCommandLineParameter(self):
        return '"' + unicode(self.value) + '"'

    def setValue(self, value):
        if value is None:
            return False
        if isinstance(value, list):
            self.value = value
            return True
        if isinstance(value, unicode):
            try:
                self.value = eval(value)
                return True
            except Exception as e:
                print unicode(e) # display error in console
                return False
        return False