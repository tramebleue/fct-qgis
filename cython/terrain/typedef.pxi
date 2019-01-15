from libcpp.queue cimport priority_queue
from libcpp.pair cimport pair
from libcpp.stack cimport stack
# from libcpp.string cimport string

ctypedef pair[long, long] Cell
ctypedef stack[Cell] CellStack
ctypedef pair[float, Cell] QueueEntry
ctypedef priority_queue[QueueEntry] CellQueue

cdef struct GradientType:
	float slope
	float aspect

ctypedef GradientType Gradient

class SilentFeedback(object):

	def setProgress(self, progress):
		pass

	def setProgressText(self, msg):
		pass

	def pushInfo(self, msg):
		pass

	def isCanceled(self):
		return False