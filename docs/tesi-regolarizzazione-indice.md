# La regolarizzazione nel machine learning: obiettivi, tecniche e trade-off bias-varianza

> Indice strutturato generato con `thesis_assistant` a partire dal Knowledge Graph accademico (corso ML).
> Le citazioni sono quelle restituite dal tool; dove l'ancoraggio è risultato debole è segnalato con ⚠️.

## Abstract

La tesi indaga il ruolo della regolarizzazione nel machine learning, analizzandone gli obiettivi
teorici e le principali tecniche operative alla luce del trade-off tra bias e varianza. Il lavoro
muove dalla scomposizione dell'errore di generalizzazione in bias², varianza e rumore irriducibile,
per mostrare come ogni scelta di regolarizzazione sposti l'equilibrio tra flessibilità del modello e
stabilità delle stime. Vengono esaminate le tecniche di penalizzazione esplicita (weight decay,
regolarizzazione L1/L2), il controllo della complessità tramite iperparametri (grado polinomiale, K
nel KNN), le tecniche di ensemble (bagging) e la regolarizzazione implicita indotta da early stopping
e data augmentation. Particolare attenzione è dedicata alla dimostrazione del perché il bagging
riduca la varianza di un fattore prossimo a 1/B solo in presenza di predittori scorrelati, e al
ruolo della correlazione ρ tra i modelli bootstrap.

---

## 1. Introduzione e motivazione

Inquadramento del problema della generalizzazione e presentazione della domanda di ricerca:
perché e come la regolarizzazione controlla il compromesso tra adattamento ai dati e capacità di
generalizzare.

- `[LEZIONE 9 — Ensemble e Bagging]` Buoni candidati: modelli instabili, con bias basso e varianza
  alta, che tendono all'overfitting — tipicamente gli alberi decisionali (non potati) e il KNN con K
  piccolo.
- `[Appunti 25_26.pdf]` …dobbiamo ridurre la flessibilità, meno varianza, ma aumenta il bias. Non si
  possono minimizzare entrambi, ecco perché trade off.

### 1.1 Contesto e rilevanza ingegneristica

Esempi applicativi in cui l'overfitting produce costi elevati e in cui la scelta dell'iperparametro
di regolarizzazione è critica per il deployment.

- `[book — Machine Learning: A First Course…, p. 260]` …comparing a logistic regression approach
  (chosen as a baseline method) to other more complicated machine learning approaches.

### 1.2 Obiettivi e contributi

(i) formalizzare il trade-off bias-varianza; (ii) classificare le tecniche di regolarizzazione;
(iii) analizzare il bagging come riduttore di varianza; (iv) derivare linee guida operative per la
selezione degli iperparametri tramite cross-validation.

- `[poly]` …aumentando α si aumenta il bias e si riduce la varianza. La scelta di α è un
  iperparametro (normalmente scelto con cross-validation).

---

## 2. Fondamenti teorici: scomposizione bias-varianza

Derivazione formale della decomposizione dell'errore quadratico atteso in bias², varianza e rumore,
con interpretazione di underfitting e overfitting.

$$\mathbb{E}\left[(z-z_0)^2\right] = \operatorname{Var}(z) + \operatorname{Bias}^2(z) + \sigma^2$$

- `[book — Machine Learning: A First Course…]` …we can re-write it in terms of the variance and the
  squared bias, E[(z − z₀)]² = E[(z − z̄) + (z̄ − z₀)]²
- `[LEZIONE 9 — Ensemble e Bagging]` Variance: dispersione delle predizioni del modello addestrato su
  uno specifico dataset attorno… al suo valore atteso
- `[Appunti 25_26.pdf, p. 32]` VARIANZA ALTA → ERRORE DI GENERALIZZAZIONE ALTO! …quanto si discosta dal
  suo valore atteso, cioè quanto cambia se cambiamo il training set.

### 2.1 Bias, varianza e rumore: definizioni
Definizioni formali e proprietà dei tre termini; esempi su regressione lineare (bias di fondo) e su
modelli flessibili (varianza elevata).

### 2.2 Legame con underfitting e overfitting
Modello rigido → bias alto, varianza bassa; modello flessibile → il contrario; l'errore totale è la
somma e si cerca una regione intermedia.

### 2.3 Il trade-off come problema di ottimizzazione
Scelta di un iperparametro di complessità che minimizzi l'errore atteso; la cross-validation come
strumento empirico di selezione.

---

## 3. Regolarizzazione parametrica: penalizzazioni e weight decay

La regolarizzazione come aggiunta di un termine di penalità alla funzione di costo. Weight decay come
decadimento esponenziale dei pesi, effetto di aumento del bias e riduzione della varianza, scelta di α
tramite cross-validation. Perché penalizzare il bias porta benefici minimi e rischio di underfitting.

- `[Appunti 25_26.pdf]` Con il weight decay, si applica un decadimento esponenziale, riducendo ad ogni
  step il valore dei pesi indipendentemente da quello che mi verrà detto dal gradiente.
- `[Appunti 25_26.pdf]` …empiricamente si è notato che applicando al bias porta a benefici minimi ed in
  più ci sta il rischio di underfitting
- `[poly]` …la scelta di α è un iperparametro (normalmente scelto con cross-validation).

### 3.1 Regolarizzazione L2 e weight decay
Forma chiusa della ridge regression; interpretazione del weight decay come contrazione dei pesi verso
zero, con effetto di smoothing della funzione appresa.

### 3.2 Regolarizzazione L1 e sparsità
Geometria della norma L1, soluzioni sparse, legame con la selezione delle feature; confronto L1/L2 in
termini di bias e varianza indotti.

### 3.3 Scelta di α e cross-validation
Procedura operativa; curva tipica bias-varianza in funzione di α.

---

## 4. Controllo della complessità nei modelli non parametrici

La regolarizzazione può essere ottenuta anche controllando la flessibilità del modello, senza
penalità esplicite.

- `[LEZIONE 2]` …K piccolo: overfitting; K grande: modello rigido e alto bias; K intermedio:
  compromesso tra dettaglio locale e stabilità.
- `[LEZIONE 5]` Feature mapping ed espansione di base; regressione polinomiale.
- `[LEZIONE 9 — Ensemble e Bagging]` …alberi decisionali (non potati) e KNN con K piccolo come modelli
  instabili ad alta varianza.

### 4.1 Espansione di base e grado polinomiale
L'aumento del grado incrementa la varianza; la selezione del grado è una forma di regolarizzazione.

### 4.2 Il parametro K nel KNN
Progressione da K piccolo (overfitting) a K grande (underfitting), con K intermedio come compromesso.

### 4.3 Potatura degli alberi decisionali
La potatura come riduzione della varianza di alberi non potati.

---

## 5. Regolarizzazione tramite ensemble: il bagging

Il bagging come media di modelli addestrati su campioni bootstrap. Il bias resta sostanzialmente
identico, la varianza si riduce. Con dataset bootstrap non si ottiene esattamente 1/B a causa della
correlazione ρ.

$$\operatorname{Var}_{\text{ens}} = \rho\sigma_f^2 + \frac{1-\rho}{B}\sigma_f^2$$

- `[LEZIONE 9]` …il bias sostanzialmente è identico e sono riuscito a ridurre la varianza di un
  fattore 1 su B.
- `[LEZIONE 9 — Ensemble e Bagging]` Perché con dataset bootstrap non si ottiene 1/B e il ruolo di ρ.
- `[Appunti 25_26.pdf]` …grazie al bagging i modelli comunque partono da dataset leggermente diversi.

### 5.1 Bootstrap e costruzione dell'ensemble
Generazione di B campioni bootstrap e media delle predizioni; il bias resta invariato.

### 5.2 Riduzione della varianza e ruolo di ρ
Al crescere di B il secondo termine svanisce ma resta ρσ²; perché i campioni bootstrap sono correlati.

### 5.3 Quando il bagging conviene
Efficace su modelli instabili ad alta varianza; inefficace su modelli stabili come la regressione
lineare.

---

## 6. Regolarizzazione implicita e boosting: cenni comparativi

- `[book — Machine Learning: A First Course…]` …each model tries to "correct" for the "mistakes" made
  by the previous ones. On the contrary to bagging, the main effect of boosting is bias reduction.

### 6.1 Bagging vs boosting: bias e varianza
Riduzione di varianza (bagging) contro riduzione di bias (boosting); implicazioni sulla scelta della
tecnica in base al modello base.

### 6.2 Early stopping e data augmentation
Arresto anticipato dell'addestramento e aumento artificiale dei dati come controllo implicito della
complessità.

- ⚠️ Citazione ancorata in modo errato dal tool: `[Appunti 25_26.pdf, p. 51]` riporta «Il secondo
  obiettivo è che la varianza deve rimanere… costante», che riguarda **l'inizializzazione di Glorot**,
  non l'early stopping. Da sostituire con: `[book — Machine Learning: A First Course…, §5.3]`
  («One such example of implicit regularization is early stopping»).

---

## 7. Discussione: trade-off, linee guida e limiti

Quadro unitario: la regolarizzazione è sempre un intervento che aumenta il bias per ridurre la
varianza; la scelta ottimale dipende dalla stabilità del modello e dalla disponibilità di dati.

- `[Appunti 25_26.pdf]` …non si possono minimizzare entrambi, ecco perché trade off.
- `[LEZIONE 9 — Ensemble e Bagging]` L'errore totale è la somma: si cerca una regione intermedia con
  poco errore.

### 7.1 Criteri di scelta della tecnica
Albero decisionale per scegliere tra penalizzazione esplicita, controllo di complessità ed ensemble,
in funzione della stabilità del modello e della dimensione del dataset.

Riferimento operativo utile (non citato dal tool, ma presente nel grafo):
`[book — Machine Learning: A First Course…, p. 240]` — «High training error? → more flexible model,
less regularization, train longer. High generalization gap? → less flexible model, more
regularization, early stopping, get more training data.»

### 7.2 Limiti e prospettive
Limiti (assenza di validazione sperimentale estesa, focus su modelli classici) e prospettive
(regolarizzazione in reti profonde, metodi bayesiani, AutoML per gli iperparametri).

---

## 8. Conclusioni

Riepilogo: formalizzazione del trade-off bias-varianza, classificazione delle tecniche, analisi del
bagging e delle sue condizioni di efficacia, linee guida operative. La regolarizzazione non è una
tecnica isolata ma un principio trasversale di **controllo della complessità**.

---

## Note di validazione dell'indice

1. **Copertura reale del grafo**: L1 e L2 sono documentate; early stopping è coperto dal libro
   (Lindholm et al., §5.3 e p. 172) e da *Understanding Deep Learning* (cap. 9); **dropout** compare
   nell'indice di UDL ma non ha chunk dedicati — il capitolo 6 andrebbe integrato o ridimensionato.
2. **Ancoraggi da verificare**: il tool ha prodotto due citazioni non pertinenti (cap. 1.2 su α,
   usata anche per L1; cap. 6.2 su early stopping). Segnalate inline.
3. **Fonti consigliate per il capitolo 3**: `poly` (Notion) e LEZIONE 5 contengono la derivazione della
   ridge regression; *Appunti 25_26.pdf* p. 51 contiene la parte su weight decay e bias.
