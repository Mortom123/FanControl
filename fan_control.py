import os
import subprocess
import re
import time

# INTERVAL=10

# DEVPATH=hwmon1=devices/platform/coretemp.0 hwmon2=devices/platform/it87.2608
# DEVNAME=hwmon1=coretemp hwmon2=it8728
# FCTEMPS=hwmon2/pwm1=hwmon1/temp1_input hwmon2/pwm2=hwmon1/temp1_input hwmon2/pwm3=hwmon1/temp1_input
# FCFANS=hwmon2/pwm1=hwmon2/fan1_input hwmon2/pwm2=hwmon2/fan2_input hwmon2/pwm3=hwmon2/fan4_input+hwmon2/fan3_input

# MINTEMP=hwmon2/pwm1=20 hwmon2/pwm2=20 hwmon2/pwm3=20
# MAXTEMP=hwmon2/pwm1=60 hwmon2/pwm2=60 hwmon2/pwm3=60
# MINSTART=hwmon2/pwm1=80 hwmon2/pwm2=80 hwmon2/pwm3=80
# MINSTOP=hwmon2/pwm1=50 hwmon2/pwm2=50 hwmon2/pwm3=50

def sanitize_8bit(no):
    if no > 255:
        no = 255
    elif no < 0:
        no = 0
    else:
        no = round(no)
    return no

def set_pwm_temp_fan(fc_params, pwm="hwmon/pwmX", temp="hwmon/tempX_input", fan="hwmon/*fanX_input",):
    attributes = fc_params.setdefault("FCTEMPS", set())
    attributes.add((pwm,temp))
    attributes = fc_params.setdefault("FCFANS", set())
    attributes.add((pwm,fan))

    return fc_params

def set_lerp_pwm(fc_params, pwm="hwmon/pwmX", mintemp=20, maxtemp=60, minstart=80, minstop=50, minpwm=0, maxpwm=255):
    """
    mintemp: below this temp, rpm = 0
    maxtemp: above this temp, rpm = 255
    minstart: rpm to start reliably
    minstop: rpm to stop reliably
    """
    mintemp = sanitize_8bit(mintemp)
    maxtemp = sanitize_8bit(maxtemp)
    minstart = sanitize_8bit(minstart)
    minstop = sanitize_8bit(minstop)

    attributes = fc_params.setdefault("MINTEMP", [])
    attributes.append((pwm, mintemp))
    attributes = fc_params.setdefault("MAXTEMP", [])
    attributes.append((pwm, maxtemp))
    attributes = fc_params.setdefault("MINSTART", [])
    attributes.append((pwm, minstart))
    attributes = fc_params.setdefault("MINSTOP", [])
    attributes.append((pwm, minstop))
    attributes = fc_params.setdefault("MINPWM", [])
    attributes.append((pwm, minpwm))
    attributes = fc_params.setdefault("MAXPWM", [])
    attributes.append((pwm, maxpwm))

    return fc_params

def set_pwm(fc_params, pwm="hwmon/pwmX", value=0):
    value = sanitize_8bit(value)
    if value > 254:
        value = 254

    set_lerp_pwm(fc_params, pwm, 0, 1, value, value, value, value + 1)
    return fc_params

def get_fc_file(fc_params):
    def get_param_value(attributes):
        sanitized_attributes = set(attributes)
        return " ".join([f"{k}={v}" for k,v in attributes])

    return "INTERVAL=10\n" + "\n".join( [f"{param}={get_param_value(value)}" for param, value in fc_params.items()])


### device specific methods ###
def set_base(fc_params):
    fc_params["DEVPATH"] = [("hwmon1","devices/platform/coretemp.0"), ("hwmon2","devices/platform/it87.2608")]
    fc_params["DEVNAME"] = [("hwmon1","coretemp"), ("hwmon2","it8728")]
    return fc_params

def set_default_pwm_fan_temp(fc_params):
    set_pwm_temp_fan(fc_params, "hwmon2/pwm1", "hwmon1/temp1_input", "hwmon2/fan1_input") # set pwm1(CPU) to manage fan1(CPU Fan) with temp1(CPU Package)
    set_pwm_temp_fan(fc_params, "hwmon2/pwm2", "hwmon1/temp1_input", "hwmon2/fan2_input") # set pwm2(SYS_FAN_1) to manage fan2(Back) with temp1(CPU Package)
    set_pwm_temp_fan(fc_params, "hwmon2/pwm3", "hwmon1/temp1_input", "hwmon2/fan3_input+hwmon2/fan4_input") # set pwm3(SYS_FAN_2, SYS_FAN_3) to manage fan3(Front) with temp1(CPU Package)
    return fc_params

def set_default_lerp_pwm(fc_params):
    set_lerp_pwm(fc_params, "hwmon2/pwm1", 20, 60, 80, 50)
    set_lerp_pwm(fc_params, "hwmon2/pwm2", 20, 60, 80, 50)
    return fc_params

def set_fc_params_default(fc_params):
    set_base(fc_params)
    set_default_pwm_fan_temp(fc_params)
    set_default_lerp_pwm(fc_params)
    return fc_params

def set_fancontrol_file(fc_params, path="/etc/fancontrol"):
    file_content = get_fc_file(fc_params)
    print(file_content)
    f = open(path,"w")
    f.write(file_content)
    f.close()
    os.system("sudo service fancontrol restart")

def calculate_pwm_gpu(temp):
    mintemp=35
    maxtemp=60
    minstart=80
    minstop=50
    minpwm=0
    maxpwm=255

    if temp < mintemp:
        return minpwm

    if temp > maxtemp:
        return maxpwm

    temp_normalized = (temp - mintemp) / (maxtemp - mintemp)
    pwm = (temp_normalized *  (maxpwm - minstart)) + minstart
    return pwm

def get_gpu_temp():
    output = str(subprocess.check_output("nvidia-smi", shell=True))
    temp = int(re.search(r'\d{1,3}(?=C)', output)[0])
    return temp

def init():
    fc_params = {}
    set_fc_params_default(fc_params)
    set_lerp_pwm(fc_params, "hwmon2/pwm3", 20, 60, 80, 50)  # set pwm3 to same as other fans
    set_fancontrol_file(fc_params)


interval = 5
cur_pwm = -1
init()
while True:
    gpu_temp = get_gpu_temp()
    pwm = calculate_pwm_gpu(gpu_temp)
    pwm = sanitize_8bit(pwm)
    print("temp", gpu_temp, "new", pwm, "old", cur_pwm)
    if pwm == 255 and cur_pwm != 255 or pwm == 0 and cur_pwm != 0:
        # we reached an extreme point
        fc_params = {}
        set_fc_params_default(fc_params)
        set_pwm(fc_params, "hwmon2/pwm3", pwm)
        cur_pwm = pwm
        set_fancontrol_file(fc_params)
        time.sleep(interval)
        continue

    if (cur_pwm - 25) < pwm < (cur_pwm + 25):
        # to small of a change, do nothing
        time.sleep(interval)
        continue

    fc_params = {}
    set_fc_params_default(fc_params)
    set_pwm(fc_params, "hwmon2/pwm3", pwm)
    cur_pwm = pwm
    set_fancontrol_file(fc_params)
    time.sleep(interval)
