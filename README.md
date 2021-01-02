# remote-mouse

Use your smartphone as a mouse and keyboard

## Usage

On the machine to be controlled:
```shell
./remote_mouse.py <port>
```

On the smartphone:
- Access `https://machine-ip:port`

## Requirements

- tornado;
- pyautogui;
- a smartphone capable of providing [device orientation](https://developer.mozilla.org/en-US/docs/Web/API/Detecting_device_orientation).

## Installation

```shell
git clone https://gitlab.com/camposm/remote-mouse
```
Next, create a folder named "keys" inside "src" and generate a self signed certificate (e.g. [this](https://www.akadia.com/services/ssh_test_certificate.html)).


