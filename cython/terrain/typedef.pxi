from libcpp.queue cimport priority_queue
from libcpp.pair cimport pair
from libcpp.stack cimport stack
from libcpp.vector cimport vector
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

cdef class ConsoleFeedback(object):

	cdef:
		int _last

	def __cinit__(self):
		self._last = 0

	@property
	def progress(self):
		return self._last
	
	cpdef void setProgress(self, int progress):
		
		if progress != self._last:
		
			self._last = progress
			self.printProgress()

			if progress == 100:
				msg = 'Done.'
				print('\r\033[K' + msg)


	cdef void printProgress(self):

		cdef int tick, i

		tick = <int>(1.0 * self._last / 100.0 * 40.0)
	
		sys.stdout.write('\r\033[K')
		
		for i in range(tick+1):
			if i % 4 == 0:
				sys.stdout.write(str(i / 4 * 10))
			else:
				sys.stdout.write('.')

		sys.stdout.flush()

	cpdef void setProgressText(self, msg):
		print('\r\033[K' + msg)
		self.printProgress()

	cpdef void pushInfo(self, msg):
		print('\r\033[K' + msg)
		self.printProgress()

	cpdef bint isCanceled(self):
		return False