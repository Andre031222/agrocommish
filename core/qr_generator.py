import qrcode


def generar_qr(device_id: str, box_size: int = 8, border: int = 2):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(device_id)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def guardar_qr(device_id: str, dest_path: str, box_size: int = 10) -> None:
    img = generar_qr(device_id, box_size=box_size)
    img.save(str(dest_path), format="PNG")
