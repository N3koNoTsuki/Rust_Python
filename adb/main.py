import time
import neko_no_lib as nl
from arduino.app_utils import App

print("Hello world!")
nl.test_meteo()


def loop():
    """This function is called repeatedly by the App framework."""
    # You can replace this with any code you want your App to run repeatedly.
    time.sleep(10)


# See: https://docs.arduino.cc/software/app-lab/tutorials/getting-started/#app-run
App.run(user_loop=loop)
