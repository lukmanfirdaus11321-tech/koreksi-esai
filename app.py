import streamlit as st
import pandas as pd
import google.generativeai as genai
import asyncio
import json
import io

st.set_page_config(page_title="Aplikasi Koreksi Esai Masal", page_icon="📝", layout="wide")

st.title("📝 Aplikasi Koreksi Esai Masal & Otomatis Per Kelas")
st.markdown("Unggah file Excel jawaban siswa, masukkan kunci jawaban, dan biarkan AI mengoreksi ratusan lembar esai secara paralel dalam hitungan detik! Hasil rekap akan terpisah otomatis per kelas beserta status Tuntas/Remedial.")

with st.sidebar:
    st.header("⚙️ Konfigurasi Sistem")
    api_key = st.text_input("Masukkan Google Gemini API Key", type="password")
    kkm = st.number_input("KKM (Kriteria Ketuntasan Minimal)", min_value=0, max_value=100, value=75)
    
    st.markdown("---")
    st.markdown("### 📋 Panduan Format Excel")
    st.markdown("File Excel (.xlsx) harus memiliki kolom:")
    st.markdown("- `Nama`: Nama lengkap siswa")
    st.markdown("- `Kelas`: Nama kelas (contoh: X-A, XI-IPA-1)")
    st.markdown("- `Jawaban`: Teks jawaban esai siswa")

uploaded_file = st.file_uploader("📂 Unggah File Data Jawaban Siswa (.xlsx)", type=["xlsx"])

rubrik = st.text_area("🔑 Kunci Jawaban & Rubrik Penilaian", placeholder="Contoh:\n1. Jelaskan proses fotosintesis... (Bobot 50: Dinilai dari ketepatan tahapan reaksi terang & gelap)\n2. Mengapa...")

if st.button("🚀 Mulai Koreksi Masal Sekarang", type="primary"):
    if not api_key:
        st.error("⚠️ Mohon masukkan Gemini API Key Anda terlebih dahulu di sidebar.")
    elif not uploaded_file:
        st.error("⚠️ Mohon unggah file Excel jawaban siswa.")
    elif not rubrik:
        st.error("⚠️ Mohon isi kunci jawaban dan rubrik penilaian.")
    else:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        try:
            df_input = pd.read_excel(uploaded_file)
            required_cols = ['Nama', 'Kelas', 'Jawaban']
            if not all(col in df_input.columns for col in required_cols):
                st.error(f"⚠️ Kolom file Excel tidak lengkap! Harus ada kolom: {required_cols}")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                async def koreksi_satu_siswa(row):
                    prompt = f"""
                    Anda adalah sistem koreksi ujian esai profesional. Berdasarkan rubrik berikut, berikan nilai integer antara 0 sampai 100 dan catatan/feedback singkat.
                    
                    Kunci Jawaban & Rubrik:
                    {rubrik}
                    
                    Jawaban Siswa ({row['Nama']} - Kelas {row['Kelas']}):
                    {row['Jawaban']}
                    
                    Kembalikan HANYA dalam format JSON valid tanpa teks tambahan di luar JSON dengan format berikut:
                    {{"nilai": <angka 0-100>, "catatan": "<feedback singkat dan objektif>"}}
                    """
                    try:
                        response = await model.generate_content_async(prompt)
                        text = response.text.strip()
                        if text.startswith("```json"):
                            text = text[7:]
                        if text.endswith("```"):
                            text = text[:-3]
                        text = text.strip()
                        
                        data = json.loads(text)
                        nilai = int(data.get('nilai', 0))
                    except Exception as e:
                        nilai = 0
                        data = {"nilai": 0, "catatan": f"Error parsing: {str(e)}"}
                    
                    status_lulus = "Tuntas" if nilai >= kkm else "Remedial"
                    return {
                        "Nama": row['Nama'],
                        "Kelas": row['Kelas'],
                        "Jawaban": row['Jawaban'],
                        "Nilai": nilai,
                        "Status": status_lulus,
                        "Catatan Guru": data.get('catatan', '')
                    }

                async def proses_semua():
                    tasks = [koreksi_satu_siswa(row) for _, row in df_input.iterrows()]
                    total = len(tasks)
                    hasil = []
                    
                    for i, coro in enumerate(asyncio.as_completed(tasks)):
                        res = await coro
                        hasil.append(res)
                        progress_bar.progress((i + 1) / total)
                        status_text.text(f"Sedang mengoreksi siswa ke-{i+1} dari {total}...")
                    return hasil

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                hasil_koreksi = loop.run_until_complete(proses_semua())
                
                df_hasil = pd.DataFrame(hasil_koreksi)
                
                st.success("✅ Koreksi Masal Selesai!")
                st.balloons()
                
                output_buffer = io.BytesIO()
                with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                    for kelas, group in df_hasil.groupby('Kelas'):
                        group.to_excel(writer, sheet_name=str(kelas), index=False)
                output_buffer.seek(0)
                
                st.markdown("### 📊 Pratinjau Rekapitulasi Nilai Keseluruhan")
                st.dataframe(df_hasil, use_container_width=True)
                
                st.download_button(
                    label="📥 Unduh Rekap Excel (Terpisah Per Kelas dalam Sheet)",
                    data=output_buffer,
                    file_name="Rekap_Nilai_Esai_Per_Kelas.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
        except Exception as e:
            st.error(f"Terjadi kesalahan saat memproses file: {str(e)}")
