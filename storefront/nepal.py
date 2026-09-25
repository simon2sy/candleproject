"""Nepal delivery data: 7 provinces and their 77 districts."""

PROVINCES = {
    "Koshi (Province 1)": [
        "Bhojpur", "Dhankuta", "Ilam", "Jhapa", "Khotang", "Morang", "Okhaldhunga",
        "Panchthar", "Sankhuwasabha", "Solukhumbu", "Sunsari", "Taplejung", "Terhathum", "Udayapur",
    ],
    "Madhesh": [
        "Bara", "Dhanusha", "Mahottari", "Parsa", "Rautahat", "Saptari", "Sarlahi", "Siraha",
    ],
    "Bagmati": [
        "Bhaktapur", "Chitwan", "Dhading", "Dolakha", "Kavrepalanchok", "Kathmandu", "Lalitpur",
        "Makwanpur", "Nuwakot", "Ramechhap", "Rasuwa", "Sindhuli", "Sindhupalchok",
    ],
    "Gandaki": [
        "Baglung", "Gorkha", "Kaski", "Lamjung", "Manang", "Mustang", "Myagdi",
        "Nawalpur", "Parbat", "Syangja", "Tanahun",
    ],
    "Lumbini": [
        "Arghakhanchi", "Banke", "Bardiya", "Dang", "Gulmi", "Kapilvastu", "Palpa",
        "Parasi", "Pyuthan", "Rolpa", "Rukum East", "Rupandehi",
    ],
    "Karnali": [
        "Dailekh", "Dolpa", "Humla", "Jajarkot", "Jumla", "Kalikot", "Mugu",
        "Rukum West", "Salyan", "Surkhet",
    ],
    "Sudurpashchim": [
        "Achham", "Baitadi", "Bajhang", "Bajura", "Dadeldhura", "Darchula", "Doti",
        "Kailali", "Kanchanpur",
    ],
}

PROVINCE_CHOICES = list(PROVINCES.keys())
