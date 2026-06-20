# Service modules

- `case_preparation.py`: persists uploaded files, identifies complete T2W MRI/CT/PET series, stores MRI and CT ranges, and calculates the PET range.
- `dicom_processing.py`: DICOM metadata parsing, series selection, ordering, and local persistence.