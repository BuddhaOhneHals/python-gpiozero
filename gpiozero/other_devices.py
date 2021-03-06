# vim: set fileencoding=utf-8:

from __future__ import (
    unicode_literals,
    print_function,
    absolute_import,
    division,
)
str = type('')


import os
import io
import subprocess
from datetime import datetime, time

from .devices import Device
from .mixins import EventsMixin


class InternalDevice(EventsMixin, Device):
    """
    Extends :class:`Device` to provide a basis for devices which have no
    specific hardware representation. These are effectively pseudo-devices and
    usually represent operating system services like the internal clock, file
    systems or network facilities.
    """


class PingServer(InternalDevice):
    """
    Extends :class:`InternalDevice` to provide a device which is active when a
    *host* on the network can be pinged.

    The following example lights an LED while a server is reachable (note the
    use of :attr:`~SourceMixin.source_delay` to ensure the server is not
    flooded with pings)::

        from gpiozero import PingServer, LED
        from signal import pause

        google = PingServer('google.com')
        led = LED(4)

        led.source_delay = 60  # check once per minute
        led.source = google

        pause()

    :param str host:
        The hostname or IP address to attempt to ping.
    """
    def __init__(self, host):
        self.host = host
        super(PingServer, self).__init__()
        self._fire_events()

    def __repr__(self):
        return '<gpiozero.PingServer host="%s">' % self.host

    @property
    def value(self):
        # XXX This is doing a DNS lookup every time it's queried; should we
        # call gethostbyname in the constructor and ping that instead (good
        # for consistency, but what if the user *expects* the host to change
        # address?)
        with io.open(os.devnull, 'wb') as devnull:
            try:
                subprocess.check_call(
                    ['ping', '-c1', self.host],
                    stdout=devnull, stderr=devnull)
            except subprocess.CalledProcessError:
                return False
            else:
                return True


class CPUTemperature(InternalDevice):
    """
    Extends :class:`InternalDevice` to provide a device which is active when
    the CPU temperature exceeds the *threshold* value.

    The following example plots the CPU's temperature on an LED bar graph::

        from gpiozero import LEDBarGraph, CPUTemperature
        from signal import pause

        # Use minimums and maximums that are closer to "normal" usage so the
        # bar graph is a bit more "lively"
        cpu = CPUTemperature(min_temp=50, max_temp=90)

        print('Initial temperature: {}C'.format(cpu.temperature))

        graph = LEDBarGraph(5, 6, 13, 19, 25, pwm=True)
        graph.source = cpu

        pause()

    :param str sensor_file:
        The file from which to read the temperature. This defaults to the
        sysfs file :file:`/sys/class/thermal/thermal_zone0/temp`. Whatever
        file is specified is expected to contain a single line containing the
        temperature in milli-degrees celsius.

    :param float min_temp:
        The temperature at which :attr:`value` will read 0.0. This defaults to
        0.0.

    :param float max_temp:
        The temperature at which :attr:`value` will read 1.0. This defaults to
        100.0.

    :param float threshold:
        The temperature above which the device will be considered "active".
        This defaults to 80.0.
    """
    def __init__(self, sensor_file='/sys/class/thermal/thermal_zone0/temp',
            min_temp=0.0, max_temp=100.0, threshold=80.0):
        self.sensor_file = sensor_file
        super(CPUTemperature, self).__init__()
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.threshold = threshold
        self._fire_events()

    def __repr__(self):
        return '<gpiozero.CPUTemperature temperature=%.2f>' % self.temperature

    @property
    def temperature(self):
        """
        Returns the current CPU temperature in degrees celsius.
        """
        with io.open(self.sensor_file, 'r') as f:
            return float(f.readline().strip()) / 1000

    @property
    def value(self):
        """
        Returns the current CPU temperature as a value between 0.0
        (representing the *min_temp* value) and 1.0 (representing the
        *max_temp* value). These default to 0.0 and 100.0 respectively, hence
        :attr:`value` is :attr:`temperature` divided by 100 by default.
        """
        temp_range = self.max_temp - self.min_temp
        return (self.temperature - self.min_temp) / temp_range

    @property
    def is_active(self):
        """
        Returns ``True`` when the CPU :attr:`temperature` exceeds the
        :attr:`threshold`.
        """
        return self.temperature > self.threshold

class LoadAverage(InternalDevice):
    """
    Extends :class:`InternalDevice` to provide a device which is active when
    the CPU load average exceeds the *threshold* value.

    The following example plots the load average on an LED bar graph::

        from gpiozero import LEDBarGraph, LoadAverage
        from signal import pause

        la = LoadAverage(min_load_average=0, max_load_average=2)
        graph = LEDBarGraph(5, 6, 13, 19, 25, pwm=True)

        graph.source = la

        pause()

    :param str load_average_file:
        The file from which to read the load average. This defaults to the
        proc file :file:`/proc/loadavg`. Whatever file is specified is expected
        to contain three space-separated load averages at the beginning of the
        file, representing 1 minute, 5 minute and 15 minute averages
        respectively.

    :param float min_load_average:
        The load average at which :attr:`value` will read 0.0. This defaults to
        0.0.

    :param float max_load_average:
        The load average at which :attr:`value` will read 1.0. This defaults to
        1.0.

    :param float threshold:
        The load average above which the device will be considered "active".
        This defaults to 0.8.

    :param int minutes:
        The number of minutes over which to average the load. Must be 1, 5 or
        15. This defaults to 5.
    """
    def __init__(self, load_average_file='/proc/loadavg', min_load_average=0.0,
        max_load_average=1.0, threshold=0.8, minutes=5):
        self.load_average_file = load_average_file
        self.min_load_average = min_load_average
        self.max_load_average = max_load_average
        self.threshold = threshold
        if minutes not in (1, 5, 15):
            raise ValueError('minutes must be 1, 5 or 15')
        self._load_average_file_column = {
            1: 0,
            5: 1,
            15: 2,
        }[minutes]
        super(LoadAverage, self).__init__()
        self._fire_events()

    def __repr__(self):
        return '<gpiozero.LoadAverage load average=%.2f>' % self.load_average

    @property
    def load_average(self):
        """
        Returns the current load average
        """
        with io.open(self.load_average_file, 'r') as f:
            file_columns = f.readline().strip().split()
            return float(file_columns[self._load_average_file_column])

    @property
    def value(self):
        """
        Returns the current load average as a value between 0.0 (representing
        the *min_load_average* value) and 1.0 (representing the
        *max_load_average* value). These default to 0.0 and 1.0 respectively.
        """
        load_average_range = self.max_load_average - self.min_load_average
        return (self.load_average - self.min_load_average) / load_average_range

    @property
    def is_active(self):
        """
        Returns ``True`` when the :attr:`load_average` exceeds the
        :attr:`threshold`.
        """
        return self.load_average > self.threshold


class TimeOfDay(InternalDevice):
    """
    Extends :class:`InternalDevice` to provide a device which is active when
    the computer's clock indicates that the current time is between
    *start_time* and *end_time* (inclusive) which are :class:`~datetime.time`
    instances.

    The following example turns on a lamp attached to an :class:`Energenie`
    plug between 7 and 8 AM::

        from gpiozero import TimeOfDay, Energenie
        from datetime import time
        from signal import pause

        lamp = Energenie(1)
        morning = TimeOfDay(time(7), time(8))

        lamp.source = morning

        pause()

    :param ~datetime.time start_time:
        The time from which the device will be considered active.

    :param ~datetime.time end_time:
        The time after which the device will be considered inactive.

    :param bool utc:
        If ``True`` (the default), a naive UTC time will be used for the
        comparison rather than a local time-zone reading.
    """
    def __init__(self, start_time, end_time, utc=True):
        self._start_time = None
        self._end_time = None
        self._utc = True
        super(TimeOfDay, self).__init__()
        self.start_time = start_time
        self.end_time = end_time
        self.utc = utc
        self._fire_events()

    def __repr__(self):
        return '<gpiozero.TimeOfDay active between %s and %s %s>' % (
                self.start_time, self.end_time, ('local', 'UTC')[self.utc])

    @property
    def start_time(self):
        """
        The time of day after which the device will be considered active.
        """
        return self._start_time

    @start_time.setter
    def start_time(self, value):
        if isinstance(value, datetime):
            value = value.time()
        if not isinstance(value, time):
            raise ValueError('start_time must be a datetime, or time instance')
        self._start_time = value

    @property
    def end_time(self):
        """
        The time of day after which the device will be considered inactive.
        """
        return self._end_time

    @end_time.setter
    def end_time(self, value):
        if isinstance(value, datetime):
            value = value.time()
        if not isinstance(value, time):
            raise ValueError('end_time must be a datetime, or time instance')
        self._end_time = value

    @property
    def utc(self):
        """
        If ``True``, use a naive UTC time reading for comparison instead of a
        local timezone reading.
        """
        return self._utc

    @utc.setter
    def utc(self, value):
        self._utc = bool(value)

    @property
    def value(self):
        if self.utc:
            return self.start_time <= datetime.utcnow().time() <= self.end_time
        else:
            return self.start_time <= datetime.now().time() <= self.end_time
