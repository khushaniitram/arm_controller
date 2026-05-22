from abc import ABC, abstractmethod

class BaseRobot(ABC):

    @abstractmethod
    def jog_joint(self,joint,direction):
        pass

    @abstractmethod
    def jog_cartesian(self,axis,direction):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def set_speed(self,speed):
        pass

    @abstractmethod
    def read_feedback(self):
        pass