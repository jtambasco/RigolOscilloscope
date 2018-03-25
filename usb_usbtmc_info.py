import os
import re

def usbtmc_info():
    root_usb = '/sys/bus/usb/drivers/usb/'
    root_usbtmc = '/sys/bus/usb/drivers/usbtmc/'
    usb_id_usbtmc = []

    filenames = os.listdir(root_usbtmc)
    matches = []
    for filename in filenames:
        match = re.search('\d-\d', filename)
        if match:
            matches.append(match.string[:-4])

    for match in matches:
        filename_vid = root_usb + match + '/idVendor'
        filename_pid = root_usb + match + '/idProduct'
        filename_ser = root_usb + match + '/serial'

        with open(filename_vid, 'r') as fs:
            vid = '0x' + fs.read().strip()
        with open(filename_pid, 'r') as fs:
            pid = '0x' + fs.read().strip()
        with open(filename_ser, 'r') as fs:
            ser = fs.read().strip()

        usbtmc_dir = os.listdir(root_usbtmc + match + ':1.0' + '/usbmisc')[0]

        usb_id_usbtmc.append([vid, pid, ser, usbtmc_dir])

    return usb_id_usbtmc

def usbtmc_from_serial(serial_number):
    info = usbtmc_info()
    found_usbtmc = None
    for _, _, serial, usbtmc in info:
        if serial == serial_number:
            found_usbtmc = usbtmc
    return found_usbtmc
