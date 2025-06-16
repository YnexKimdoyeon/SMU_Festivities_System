import qrcode

img = qrcode.make("http://ynexdoyeonkim.kro.kr/")
img.save("simple_qr.png")
