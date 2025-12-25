# 📋 Dokumentasi Sistem Skrining Gizi & Stunting Anak

## 🎯 Fitur Utama

### 1. **Sistem Autentikasi**
- Login dengan username dan password
- 2 Role: Admin dan User
- Session management

### 2. **Form Skrining Gizi**
- Input data anak (nama, usia, gender)
- Input hasil pengukuran (BB, TB, LK)
- Perhitungan otomatis Z-Score berdasarkan standar WHO
- Analisis status gizi dan stunting
- Simpan otomatis ke database

### 3. **Database Management** (Khusus Admin)
- Melihat semua data pengukuran
- Filter berdasarkan gender dan status
- Search berdasarkan nama anak
- Statistik ringkasan (total pengukuran, risiko stunting, dll)
- Export data ke CSV

### 4. **Panduan Cara Pengukuran**
- Panduan lengkap pengukuran Berat Badan
- Panduan pengukuran Panjang/Tinggi Badan
- Panduan pengukuran Lingkar Kepala
- Tips dan best practices

## 🔐 Default Login

### Admin
- **Username:** `admin`
- **Password:** `admin123`
- **Akses:** Semua fitur termasuk database

### User
- **Username:** `user`
- **Password:** `user123`
- **Akses:** Form skrining dan panduan pengukuran

## 📊 Database

Sistem menggunakan SQLite dengan 2 tabel utama:

### Tabel `users`
- id, username, password, role, nama_lengkap

### Tabel `measurements`
- Data pengukuran lengkap
- Z-Score untuk semua indikator (WFA, HFA, WFH, HCFA)
- Status gizi dan stunting
- Informasi siapa yang input data
- Timestamp

## 🚀 Cara Menjalankan

```bash
streamlit run krenova.py
```

## 📁 File Database

Database akan otomatis dibuat dengan nama: `krenova_data.db`

## 🎨 Fitur UI/UX

- ✅ Design modern dengan custom CSS
- ✅ Responsive layout
- ✅ Color-coded status (success/warning/error)
- ✅ Card-based metrics display
- ✅ Gradient styling untuk highlight
- ✅ User-friendly navigation

## 📈 Indikator yang Diukur

1. **WFA (Weight for Age)** - Berat Badan menurut Usia
2. **HFA (Height for Age)** - Tinggi Badan menurut Usia
3. **WFH (Weight for Height)** - Berat Badan menurut Tinggi
4. **HCFA (Head Circumference for Age)** - Lingkar Kepala menurut Usia

## ⚠️ Catatan Penting

- Semua pengukuran disimpan otomatis ke database
- Hanya admin yang dapat melihat database
- Data dapat diexport dalam format CSV
- Hasil merupakan skrining awal, perlu konsultasi lanjutan dengan tenaga kesehatan

## 🔧 Dependencies

- streamlit
- pandas
- numpy
- sqlite3
- hashlib

## 📞 Support

Untuk bantuan lebih lanjut, hubungi administrator sistem.
