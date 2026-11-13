-- MySQL DDL generated from aemigrate.db (single source of truth)

CREATE TABLE patients (
	patient_id VARCHAR(10) NOT NULL, 
	initials VARCHAR(5), 
	dob DATE, 
	sex VARCHAR(1), 
	weight_kg NUMERIC(5, 1), 
	PRIMARY KEY (patient_id)
)ENGINE=InnoDB CHARSET=utf8mb4;

CREATE TABLE reporters (
	reporter_id VARCHAR(10) NOT NULL, 
	name VARCHAR(100), 
	reporter_type VARCHAR(20), 
	country VARCHAR(2), 
	PRIMARY KEY (reporter_id), 
	CONSTRAINT uq_reporter UNIQUE (name, reporter_type, country)
)ENGINE=InnoDB CHARSET=utf8mb4;

CREATE TABLE cases (
	case_id VARCHAR(10) NOT NULL, 
	receive_date DATE NOT NULL, 
	seriousness VARCHAR(12) NOT NULL, 
	outcome VARCHAR(20), 
	patient_id VARCHAR(10) NOT NULL, 
	reporter_id VARCHAR(10) NOT NULL, 
	PRIMARY KEY (case_id), 
	FOREIGN KEY(patient_id) REFERENCES patients (patient_id), 
	FOREIGN KEY(reporter_id) REFERENCES reporters (reporter_id)
)ENGINE=InnoDB CHARSET=utf8mb4;

CREATE TABLE drugs (
	drug_row_id INTEGER NOT NULL AUTO_INCREMENT, 
	case_id VARCHAR(10) NOT NULL, 
	drug_code VARCHAR(10) NOT NULL, 
	drug_name VARCHAR(60), 
	dose_mg NUMERIC(8, 2), 
	therapy_start DATE, 
	therapy_end DATE, 
	PRIMARY KEY (drug_row_id), 
	FOREIGN KEY(case_id) REFERENCES cases (case_id)
)ENGINE=InnoDB CHARSET=utf8mb4;

CREATE TABLE events (
	event_row_id INTEGER NOT NULL AUTO_INCREMENT, 
	case_id VARCHAR(10) NOT NULL, 
	event_code VARCHAR(10) NOT NULL, 
	event_term VARCHAR(60), 
	onset_date DATE, 
	PRIMARY KEY (event_row_id), 
	FOREIGN KEY(case_id) REFERENCES cases (case_id)
)ENGINE=InnoDB CHARSET=utf8mb4;
