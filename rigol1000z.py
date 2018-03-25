import time
import usbtmc
import os
import numpy as np
import tqdm
from usb_usbtmc_info import usbtmc_info

class _Usbtmc:
    """
    Simple usbmtc device
    """

    def __init__(self, vid, pid):
        self.file = usbtmc.Instrument(vid, pid)

    def _write(self, cmd):
        ret = self.file.write(cmd)
        time.sleep(0.3)
        return ret

    def _read(self, num_bytes=-1):
        return self.file.read(num_bytes).strip()

    def _read_raw(self, num_bytes=-1):
        return self.file.read_raw(num_bytes)

    def _ask(self, cmd, num_bytes=-1):
        self._write(cmd)
        return self._read(num_bytes)

    def _ask_raw(self, cmd, num_bytes=-1):
        self._write(cmd)
        return self._read_raw(num_bytes)

class _Rigol1054zChannel:
    def __init__(self, channel, osc):
        self._channel = channel
        self._osc = osc

    def _write(self, cmd):
        return self._osc._write(':chan%i%s' % (self._channel, cmd))

    def _read(self):
        return self._osc._read()

    def _ask(self, cmd):
        self._write(cmd)
        r = self._read()
        return r

    def get_voltage_rms_V(self):
        channel = int(channel)
        assert 1 <= channel <= 4, 'Invalid channel.'
        return self._osc.ask(':MEAS:ITEM? VRMS,CHAN%i' % channel)

    def select_channel(self):
        self._osc.write(':MEAS:SOUR CHAN%i' % self._channel)
        return self._osc.selected_channel()

    def get_coupling(self):
        return self._ask(':coup?')

    def set_coupling(self, coupling):
        coupling = coupling.upper()
        assert coupling in ('AC', 'DC', 'GND')
        self._write(':coup %s' % coupling)
        return self.get_coupling()

    def enable(self):
        self._write(':disp 1' % self._channel)
        return self.enabled()

    def disable(self):
        self._write(':disp 0' % self._channel)
        return self.disabled()

    def enabled(self):
        return bool(int(self._ask(':disp?')))

    def disabled(self):
        return bool(int(self._ask(':disp?'))) ^ 1

    def get_offset_V(self):
        return float(self._ask(':off?'))

    def set_offset_V(self, offset):
        assert -1000 <= offset <= 1000.
        self._write(':off %.4e' % offset)
        return self.get_offset_V()

    def get_range_V(self):
        return self._ask(':rang?')

    def set_range_V(self, range):
        assert 8e-3 <= range <= 800.
        self._write(':rang %.4e' % range)
        return self.get_range_V()

    def set_vertical_scale_V(self, scale):
        assert 1e-3 <= scale <= 100
        self._write(':scal %.4e' % scale)

    def get_probe_ratio(self):
        return float(self._ask(':prob?'))

    def set_probe_ratio(self, ratio):
        assert ratio in (0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1,\
                         2, 5, 10, 20, 50, 100, 200, 500, 1000)
        self._write(':prob %s' % ratio)
        return self.get_probe_ratio()

    def get_units(self):
        return self._ask(':unit?')

    def set_units(self, unit):
        unit = unit.lower()
        assert unit in ('volt', 'watt', 'amp', 'unkn')
        self._write(':unit %s' % unit)

    def get_data_premable(self):
        pre = self._osc._ask(':wav:pre?').split(',')
        print(pre)
        pre_dict = {
            'format': int(pre[0]),
            'type': int(pre[1]),
            'points': int(pre[2]),
            'count': int(pre[3]),
            'xincrement': float(pre[4]),
            'xorigin': float(pre[5]),
            'xreference': float(pre[6]),
            'yincrement': float(pre[7]),
            'yorigin': float(pre[8]),
            'yreference': float(pre[9]),
        }
        return pre_dict

    def get_data(self, mode='norm', filename=None):
        assert mode in ('norm', 'max', 'raw')

        # Setup scope
        self._osc._write(':stop')
        self._osc._write(':wav:sour chan%i' % self._channel)
        self._osc._write(':wav:mode %s' % mode)
        self._osc._write(':wav:form byte')

        info = self.get_data_premable()

        max_num_pts = 250000
        num_blocks = info['points'] // max_num_pts
        last_block_pts = info['points'] % max_num_pts

        datas = []
        for i in tqdm.tqdm(range(num_blocks+1), ncols=60):
            if i < num_blocks:
                self._osc._write(':wav:star %i' % (1+i*250000))
                self._osc._write(':wav:stop %i' % (250000*(i+1)))
            else:
                if last_block_pts:
                    self._osc._write(':wav:star %i' % (1+num_blocks*250000))
                    self._osc._write(':wav:stop %i' % (num_blocks*250000+last_block_pts))
                else:
                    break
            data = self._osc._ask_raw(':wav:data?')[11:]
            data = np.frombuffer(data, 'B')
            datas.append(data)

        datas = np.concatenate(datas)
        v = (datas - info['yorigin'] - info['yreference']) * info['yincrement']

        t = np.arange(0, info['points']*info['xincrement'], info['xincrement'])
        # info['xorigin'] + info['xreference']

        if filename:
            try:
                os.remove(filename)
            except OSError:
                pass
            np.savetxt(filename, np.c_[t, v], '%.12e', ',')

        return t, v

class _Rigol1054zTrigger:
    def __init__(self, osc):
        self._osc = osc

    def get_trigger_level_V(self):
        return self._osc._ask(':trig:edg:lev?')

    def set_trigger_level_V(self, level):
        self._osc._write(':trig:edg:lev %.3e' % level)
        return self.get_trigger_level_V()

    def get_trigger_holdoff_s(self):
        return self._osc._ask(':trig:hold?')

    def set_trigger_holdoff_s(self, holdoff):
        self._osc._write(':trig:hold %.3e' % holdoff)
        return self.get_trigger_holdoff_s()

class _Rigol1054zTimebase:
    def __init__(self, osc):
        self._osc = osc

    def _write(self, cmd):
        return self._osc._write(':tim%s' % cmd)

    def _read(self):
        return self._osc._read()

    def _ask(self, cmd):
        self._write(cmd)
        r = self._read()
        return r

    def get_timebase_scale_s_div(self):
        return float(self._ask(':scal?'))

    def set_timebase_scale_s_div(self, timebase):
        assert 50e-9 <= timebase <= 50
        self._write(':scal %.4e' % timebase)
        return self.get_timebase_scale_s_div()

    def get_timebase_mode(self):
        return self._ask(':mode?')

    def set_timebase_mode(self, mode):
        mode = mode.lower()
        assert mode in ('main', 'xy', 'roll')
        self._write(':mode %s' % mode)
        return get_timebase_scale()

    def get_timebase_offset_s(self):
        return self._ask(':offs?')

    def set_timebase_offset_s(self, offset):
        self._write(':offs %.4e' % -offset)
        return self.get_timebase_offset_s()

class Rigol1054z(_Usbtmc):
    def __init__(self):
        # If the device is rebooted, the python-usbtmc driver won't work.
        # Somehow, by sending any command using the kernel driver, then
        # python-usbtmc works with this scope.  The following searches
        # the usbtmc numbers and finds the corresponding usb pid, vid
        # and serial, and then issues a command via the kernel driver.
        rigol_vid = '0x1ab1'
        rigol_pid = '0x04ce'
        usb_id_usbtmc = usbtmc_info()
        for dev in usb_id_usbtmc:
            if dev[0] == rigol_vid and dev[1] == rigol_pid:
                os.system('echo *IDN? >> /dev/%s' % dev[3])

        _Usbtmc.__init__(self, int(rigol_vid, 16), int(rigol_pid, 16))

        self._channels = [_Rigol1054zChannel(c, self) for c in range(1,5)]
        self.trigger = _Rigol1054zTrigger(self)
        self.timebase = _Rigol1054zTimebase(self)

    def __getitem__(self, i):
        assert 1 <= i <= 4, 'Not a valid channel.'
        return self._channels[i-1]

    def __len__(self):
        return len(self._channels)

    def autoscale(self):
        self._write(':aut')

    def clear(self):
        self._write(':clear')

    def run(self):
        self._write(':run')

    def stop(self):
        self._write(':stop')

    def force(self):
        self._write(':tfor')

    def set_single_shot(self):
        self._write(':sing')

    def get_id(self):
        return self._ask('*IDN?')

    def get_averaging(self):
        return self._ask(':acq:aver?')

    def set_averaging(self, count):
        assert count in [2**n for n in range(1, 11)]
        self._write(':acq:aver %i' % count)
        return self.get_averaging()

    def set_averaging_mode(self):
        self._write(':acq:type aver')
        return self.get_mode()

    def set_normal_mode(self):
        self._write(':acq:type norm')
        return self.get_mode()

    def set_high_resolution_mode(self):
        self._write(':acq:type hres')
        return self.get_mode()

    def set_peak_mode(self):
        self._write(':acq:type peak')
        return self.get_mode()

    def get_mode(self):
        modes = {
            'NORM': 'normal',
            'AVER': 'averages',
            'PEAK': 'peak',
            'HRES': 'high_resolution'
        }
        return modes[self._ask(':acq:type?')]

    def get_sampling_rate(self):
        return float(self._ask(':acq:srat?'))

    def get_memory_depth(self):
        md = self._ask(':acq:mdep?')
        if md != 'AUTO':
           md = int(md)
        return md

    def set_memory_depth(self, pts):
        num_enabled_chans = sum(self.get_channels_enabled())
        if pts != 'AUTO':
            pts = int(pts)

        if num_enabled_chans == 1:
            assert pts in ('AUTO', 12000, 120000, 1200000, 12000000, 24000000)
        elif num_enabled_chans == 2:
            assert pts in ('AUTO', 6000, 60000, 600000, 6000000, 12000000)
        elif num_enabled_chans in (3, 4):
            assert pts in ('AUTO', 3000, 30000, 300000, 3000000, 6000000)

        self.run()
        if pts == 'AUTO':
            r = self._write(':acq:mdep AUTO')
        else:
            r = self._write(':acq:mdep %s' % pts)
        return r

    def get_channels_enabled(self):
        return [c.enabled() for c in self._channels]

    def selected_channel(self):
        return self._ask(':MEAS:SOUR?')

    def get_screenshot(self, filename, type='png'):
        self.file.timeout = 0
        self._write(':disp:data? on,off,%s' % type)

        assert type in ('jpeg', 'png', 'bmp8', 'bmp24', 'tiff')

        if type == 'jpeg':
            s = 3
        elif type == 'png':
            s = 0.5
        elif type == 'bmp8':
            s = 0.5
        elif type == 'bmp24':
            s = 0.5
        elif type == 'tiff':
            s = 0.5
        time.sleep(s)
        raw_img = self._read_raw(3850780)[11:-4]

        with open(filename, 'wb') as fs:
            fs.write(raw_img)

        return raw_img
