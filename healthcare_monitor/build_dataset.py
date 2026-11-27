"""Builds the datasets used by the NLP symptom agent.

NOTE: Datasets are curated/synthetic (no internet access to Kaggle here). 
  data/disease_knowledge.csv  - disease -> symptoms, specialty, severity, precautions
  data/symptom_corpus.csv     - natural-language complaints labelled with disease
  data/doctors.csv            - seed doctors
Replace/extend with a real dataset (e.g. Kaggle 'Disease Symptom Prediction') by keeping the same columns.
"""
import csv, random
random.seed(42)

D = [
 # disease, specialty, severity(1-5), symptoms, precautions
 ("Common Cold","General Physician",1,["runny nose","sneezing","sore throat","cough","mild fever","congestion"],"rest;drink warm fluids;steam inhalation;wash hands"),
 ("Influenza","General Physician",2,["high fever","body ache","chills","fatigue","cough","headache","sore throat"],"rest;hydrate;paracetamol for fever;see doctor if worse"),
 ("COVID-19","General Physician",3,["fever","dry cough","loss of smell","loss of taste","fatigue","shortness of breath","body ache"],"isolate;test;monitor oxygen;consult doctor"),
 ("Migraine","Neurologist",2,["severe headache","nausea","sensitivity to light","blurred vision","vomiting","throbbing pain"],"rest in dark room;hydrate;avoid triggers;consult neurologist"),
 ("Tension Headache","General Physician",1,["headache","neck pain","stress","tight band around head","fatigue"],"rest;reduce stress;hydrate;posture check"),
 ("Gastroenteritis","Gastroenterologist",2,["diarrhea","vomiting","stomach pain","nausea","fever","dehydration"],"oral rehydration;bland diet;avoid dairy;see doctor if blood in stool"),
 ("Food Poisoning","Gastroenterologist",2,["vomiting","diarrhea","stomach cramps","nausea","fever","weakness"],"hydrate;rest;avoid solid food briefly;seek care if severe"),
 ("GERD (Acid Reflux)","Gastroenterologist",2,["heartburn","acid taste in mouth","chest burning","bloating","difficulty swallowing","burping"],"avoid spicy food;eat small meals;do not lie down after eating"),
 ("Hypertension","Cardiologist",3,["headache","dizziness","blurred vision","chest pain","nosebleed","shortness of breath"],"reduce salt;exercise;monitor BP;take prescribed medication"),
 ("Heart Attack","Cardiologist",5,["severe chest pain","pain in left arm","shortness of breath","cold sweat","nausea","jaw pain","dizziness"],"CALL EMERGENCY SERVICES;chew aspirin if not allergic;stay calm"),
 ("Stroke","Neurologist",5,["face drooping","arm weakness","slurred speech","sudden confusion","sudden vision loss","severe headache","loss of balance"],"CALL EMERGENCY SERVICES;note time of onset;do not give food or drink"),
 ("Type 2 Diabetes","Endocrinologist",3,["increased thirst","frequent urination","fatigue","blurred vision","slow healing wounds","weight loss","hunger"],"monitor glucose;low sugar diet;exercise;consult endocrinologist"),
 ("Hypothyroidism","Endocrinologist",2,["fatigue","weight gain","cold intolerance","dry skin","hair loss","constipation","depression"],"thyroid tests;medication adherence;regular follow up"),
 ("Asthma","Pulmonologist",3,["wheezing","shortness of breath","chest tightness","cough at night","difficulty breathing"],"use inhaler;avoid triggers;keep rescue inhaler handy"),
 ("Pneumonia","Pulmonologist",4,["high fever","productive cough","chest pain","shortness of breath","chills","fatigue","rapid breathing"],"see doctor urgently;rest;fluids;antibiotics as prescribed"),
 ("Bronchitis","Pulmonologist",2,["persistent cough","mucus","chest discomfort","fatigue","mild fever","wheezing"],"rest;fluids;avoid smoke;humidifier"),
 ("Urinary Tract Infection","Urologist",2,["burning urination","frequent urination","lower abdominal pain","cloudy urine","blood in urine","urgency"],"drink water;see doctor for antibiotics;hygiene"),
 ("Dengue","General Physician",4,["high fever","severe headache","pain behind eyes","joint pain","skin rash","muscle pain","nausea"],"hydrate;platelet monitoring;avoid aspirin;seek care early"),
 ("Malaria","General Physician",4,["fever with chills","sweating","headache","nausea","vomiting","muscle pain","fatigue"],"blood test;antimalarial treatment;mosquito protection"),
 ("Typhoid","General Physician",3,["prolonged fever","abdominal pain","weakness","constipation","headache","loss of appetite","rose spots"],"safe water;antibiotics;rest;hygiene"),
 ("Allergic Rhinitis","ENT Specialist",1,["sneezing","itchy eyes","runny nose","nasal congestion","itchy throat","watery eyes"],"avoid allergens;antihistamines;saline rinse"),
 ("Sinusitis","ENT Specialist",2,["facial pain","nasal congestion","thick nasal discharge","headache","reduced smell","pressure around eyes"],"steam;saline rinse;fluids;see doctor if >10 days"),
 ("Eczema","Dermatologist",1,["itchy skin","dry skin","red patches","skin inflammation","rash","skin cracking"],"moisturize;avoid irritants;mild soap"),
 ("Acne","Dermatologist",1,["pimples","blackheads","oily skin","skin inflammation","scarring"],"gentle cleansing;avoid picking;see dermatologist"),
 ("Anemia","General Physician",2,["fatigue","pale skin","dizziness","cold hands","shortness of breath","headache","brittle nails"],"iron rich diet;blood test;supplements as advised"),
 ("Depression","Psychiatrist",3,["persistent sadness","loss of interest","sleep problems","fatigue","hopelessness","poor concentration","appetite change"],"talk to someone you trust;seek professional help;routine and exercise"),
 ("Anxiety Disorder","Psychiatrist",2,["excessive worry","restlessness","palpitations","sweating","trouble sleeping","trembling","irritability"],"breathing exercises;limit caffeine;seek therapy"),
 ("Arthritis","Orthopedist",2,["joint pain","joint stiffness","swelling in joints","reduced movement","morning stiffness","fatigue"],"gentle exercise;heat therapy;medication;physio"),
 ("Appendicitis","General Surgeon",5,["severe lower right abdominal pain","nausea","vomiting","fever","loss of appetite","abdominal swelling"],"GO TO EMERGENCY;do not eat or drink;do not take painkillers blindly"),
 ("Kidney Stones","Urologist",3,["severe back pain","pain in side","blood in urine","painful urination","nausea","vomiting"],"drink water;pain relief;see doctor for imaging"),
 ("Conjunctivitis","Ophthalmologist",1,["red eyes","itchy eyes","watery eyes","eye discharge","gritty feeling in eye","swollen eyelids"],"avoid touching eyes;clean discharge;hand hygiene"),
 ("Anaphylaxis","Emergency Medicine",5,["swelling of face","difficulty breathing","hives","rapid pulse","dizziness","throat tightening","wheezing"],"CALL EMERGENCY SERVICES;use epinephrine auto-injector if available"),
]

SYN = {"fever":["fever","temperature","feeling feverish"],"headache":["headache","head pain","head hurts"],
 "cough":["cough","coughing"],"fatigue":["fatigue","tiredness","feeling exhausted","low energy"],
 "nausea":["nausea","feeling nauseous","queasy"],"vomiting":["vomiting","throwing up"],
 "diarrhea":["diarrhea","loose motions","watery stools"],"shortness of breath":["shortness of breath","breathlessness","can't breathe properly"]}
TEMPL = ["I have {s}.","I've been having {s} for {d} days.","Suffering from {s} since {d} days.","My main problem is {s}.",
         "For the past {d} days I am experiencing {s}.","Doctor, I feel {s}.","Lately there is {s}.","I am worried about {s}."]

def phrase(sym): return random.choice(SYN.get(sym,[sym]))
def join(items): return items[0] if len(items)==1 else ", ".join(items[:-1])+" and "+items[-1]

rows=[]
for dis,_,_,syms,_ in D:
    for _ in range(90):
        k=random.randint(2,min(5,len(syms)))
        chosen=random.sample(syms,k)
        txt=random.choice(TEMPL).format(s=join([phrase(s) for s in chosen]),d=random.randint(1,7))
        if random.random()<0.15:  # add noise symptom
            txt+=" Also "+phrase(random.choice(random.choice(D)[3]))+"."
        rows.append((txt,dis))
random.shuffle(rows)
with open("data/symptom_corpus.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["text","disease"]); w.writerows(rows)
with open("data/disease_knowledge.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["disease","specialty","severity","symptoms","precautions"])
    for dis,sp,sev,syms,prec in D: w.writerow([dis,sp,sev,";".join(syms),prec])

DOC=[("Dr. Anjali Sharma","General Physician",12,4.7,"Mon,Tue,Wed,Thu,Fri"),("Dr. Rohit Verma","General Physician",8,4.4,"Mon,Wed,Fri,Sat"),
("Dr. Meera Nair","Cardiologist",18,4.9,"Mon,Tue,Thu"),("Dr. Arjun Rao","Cardiologist",10,4.5,"Wed,Fri,Sat"),
("Dr. Kavita Iyer","Neurologist",15,4.8,"Tue,Thu,Fri"),("Dr. Sameer Khan","Gastroenterologist",11,4.6,"Mon,Wed,Thu"),
("Dr. Priya Menon","Endocrinologist",14,4.7,"Mon,Tue,Fri"),("Dr. Vikram Singh","Pulmonologist",16,4.6,"Tue,Wed,Sat"),
("Dr. Neha Gupta","Dermatologist",9,4.5,"Mon,Thu,Fri"),("Dr. Rajesh Pillai","ENT Specialist",13,4.3,"Mon,Tue,Wed"),
("Dr. Sunita Reddy","Psychiatrist",17,4.8,"Tue,Thu,Sat"),("Dr. Manoj Patel","Orthopedist",20,4.7,"Mon,Wed,Fri"),
("Dr. Farah Ali","Urologist",10,4.4,"Tue,Thu,Fri"),("Dr. Ashok Das","Ophthalmologist",22,4.9,"Mon,Tue,Thu"),
("Dr. Lakshmi Bhat","General Surgeon",19,4.6,"Wed,Thu,Sat"),("Dr. Imran Qureshi","Emergency Medicine",14,4.5,"Mon,Tue,Wed,Thu,Fri,Sat,Sun")]
with open("data/doctors.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["name","specialty","experience","rating","days"]); w.writerows(DOC)
print(len(rows),"corpus rows;",len(D),"diseases;",len(DOC),"doctors")
