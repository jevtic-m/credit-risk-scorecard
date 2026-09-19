# Interview-Notizen

Die Fragen sind typische Interviewfragen zu jedem Arbeitspaket. Jede Antwort bezieht sich auf die echten
Ergebnisse dieses Repos (Zahlen aus `reports/ap1_summary.md` und `reports/findings.md`).

---

## Nach AP1 (Daten)

**Warum schließt du laufende Kredite aus?**

Bei laufenden Krediten (Current, Late, In Grace Period) ist noch nicht bekannt, ob sie zurückgezahlt
werden oder ausfallen. Das sind 912.569 der 2,26 Mio. Kredite, also 40 %. Würde ich sie als "gut"
werten, läge die Ausfallquote bei etwa 12 % statt bei den tatsächlichen 19,98 % der abgeschlossenen
Kredite. Das ist ein Zensierungsproblem: Man sieht das Ergebnis noch nicht, darf es aber nicht mit
"kein Ausfall" verwechseln.

**Was ist Datenleckage und welche Spalten waren bei dir betroffen?**

Datenleckage heißt, dass das Modell Informationen benutzt, die es zum Entscheidungszeitpunkt gar nicht
haben kann. Bei Lending Club sind das alle Spalten, die erst während der Laufzeit oder nach einem Ausfall
entstehen. Ich habe 38 Spalten explizit ausgeschlossen: Zahlungen und Rückflüsse (`total_pymnt`,
`total_rec_prncp`, `total_rec_int`), Verwertungserlöse (`recoveries`), letzte und nächste Zahlung,
offener Restsaldo (`out_prncp`), später neu abgerufene FICO-Werte (`last_fico_range_*`), 15
Härtefall-Spalten und 7 Vergleichs-Spalten (`settlement_*`). Die Liste steht als Python-Liste im Code,
und das Skript bricht ab, wenn ein Name darin nicht in der Rohdatei existiert.

**Warum ist `recoveries` problematisch, obwohl es doch Information über den Verlust enthält?**

`recoveries` ist der Betrag, den die Bank nach einem Ausfall noch eintreiben konnte. Der Wert ist nur bei
ausgefallenen Krediten größer als null. Ein Modell, das diese Spalte sieht, würde den Ausfall daran fast
perfekt "erkennen", aber bei einem neuen Antrag ist der Wert immer null, weil noch nichts passiert ist.
Für die Ausfallwahrscheinlichkeit ist die Spalte deshalb wertlos und gefährlich. Für die Verlusthöhe
nach Ausfall (LGD) ist sie dagegen genau richtig, weil dort der Ausfall schon eingetreten ist. Deshalb
liegt sie in einer eigenen Datei (`lgd_inputs.parquet`, nur die 269.360 ausgefallenen Kredite) und nicht
in den Modelldaten.

**Zusatzfrage, die sich aus den Daten ergibt: Warum ist die Ausfallquote des Jahrgangs 2018 mit
15,76 % niedriger als die von 2016 mit 23,29 %?**

Weil von 2018 erst 56.318 von 495.242 Krediten abgeschlossen sind, also 11 %. Abgeschlossen sind
bisher vor allem Kredite, die sehr früh zurückgezahlt oder sehr früh ausgefallen sind. Der Jahrgang ist
nicht ausgereift, die Quote ist deshalb nicht vergleichbar. In AP2 wird das über die Vintage-Analyse mit
Reifegrad-Hinweis sauber behandelt.

---

## Nach AP2 (SQL)

**Was ist eine Vintage-Analyse und wozu braucht man sie?**

Eine Vintage-Analyse gruppiert Kredite nach ihrem Ausgabezeitraum (Jahrgang, Quartal) und vergleicht,
wie sich die Ausfallquote je Jahrgang entwickelt. Man braucht sie, um zu erkennen, ob sich die Qualität
des Neugeschäfts verändert hat, unabhängig davon, wie groß das Portfolio insgesamt ist. In diesem
Repo zeigt sie zum Beispiel, dass die 36-Monats-Kredite von 2010 bis 2015 langsam von 10,9 % auf
14,9 % Ausfallquote gestiegen sind, während das Neugeschäft je Quartal um mehr als das Zehnfache
gewachsen ist.

**Warum ist die Ausfallquote der Vintages von 2018 niedriger als die von 2014?**

Weil der Datensatz im Dezember 2018 endet und die Kredite von 2018 ihre Laufzeit noch gar nicht
durchlaufen haben. In den Daten mit bekanntem Ausgang stehen von 2018 nur 56.318 von 495.242 Krediten,
und zwar die, die früh zurückgezahlt oder früh ausgefallen sind. Die Quote von 15,8 % sagt deshalb
nichts über den Jahrgang aus. Vergleichbar sind nur ausgereifte Jahrgänge: 36-Monats-Kredite bis 2015,
60-Monats-Kredite bis 2013. Bei 2014 ist die Quote der abgeschlossenen Kredite sogar höher (18,45 %) als
die der ausgereiften (13,73 %), weil die noch laufenden 60-Monats-Kredite in der ausgereiften Menge fehlen.

**Wann brauchst du eine Window Function statt GROUP BY?**

GROUP BY verdichtet mehrere Zeilen zu einer Zeile pro Gruppe. Eine Window Function rechnet über eine
Gruppe von Zeilen, lässt die Zeilen aber bestehen. Ich brauche sie, wenn eine Zeile einen Wert aus
anderen Zeilen sehen muss: In Abfrage 13 holt LAG den Vorjahreswert in dieselbe Zeile, um die Veränderung
zu berechnen. In Abfrage 15 bildet SUM() OVER (ORDER BY grade) die kumulierte Summe von A nach G, so dass
in der Zeile für C steht, dass A bis C 71,5 % des Volumens sind. Mit GROUP BY allein ginge beides nicht.

---

## Nach AP3 (Binning)

**Was ist Weight of Evidence und warum passt es zur logistischen Regression?**

WoE eines Bins ist der Logarithmus aus "Anteil der Guten im Bin" geteilt durch "Anteil der Schlechten im
Bin". Bei fico_range_low ab 752 ist der WoE zum Beispiel +1,06 (nur 7,3 % Ausfälle), unter 662 ist er
-0,38 (24,8 % Ausfälle). Die logistische Regression modelliert genau die Log-Odds, also den Logarithmus
des Verhältnisses gut zu schlecht. WoE bringt jede Variable, egal ob Zahl oder Kategorie, auf dieselbe
Log-Odds-Skala. Dadurch braucht die Regression keine Dummy-Variablen und die Koeffizienten sind direkt
vergleichbar.

**Ab welchem IV wirst du misstrauisch statt zufrieden?**

Ab 0,5. Im Kreditrisiko ist keine einzelne Antragsvariable so stark, dass sie allein den Ausfall fast
erklärt. Ein IV über 0,5 heißt fast immer, dass die Variable Wissen aus der Zukunft enthält, zum Beispiel
Rückzahlungen. In meinem Hauptmodell liegt die stärkste Variable, term_months, bei 0,238. Selbst Lending
Clubs eigene Einstufung sub_grade kommt nur auf 0,498, und die ist ja schon ein ganzes Modell. Wenn eine
meiner Variablen 0,8 hätte, würde ich zuerst nach dem Datenfehler suchen, nicht feiern.

**Warum imputierst du fehlende Werte nicht?**

Weil "fehlt" im Kreditrisiko selbst eine Information ist. optbinning legt für jede Variable einen eigenen
Missing-Bin an und schätzt dessen Ausfallquote. Bei acc_open_past_24mths fehlt der Wert bei 50.030
Trainingskrediten, und diese Gruppe hat mit 15,3 % eine deutlich andere Ausfallquote als der
Durchschnitt von 18,5 %. Würde ich den Median einsetzen, würde ich diese Gruppe in einen Bin mischen, zu
dem sie nicht gehört, und die Information verlieren.

**Warum hast du zeitbasiert statt zufällig gesplittet?**

Weil das Modell im Einsatz künftige Kredite bewertet, nicht eine Zufallsstichprobe der Vergangenheit. Ich
trainiere auf 2007 bis 2015 (829.355 Kredite) und teste auf 2016 bis 2018 (518.744 Kredite). Ein
zufälliger Split hätte Kredite aus demselben Monat in beide Teile gelegt, und das Modell hätte davon
profitiert, dass sich Konjunktur und Vergabepolitik in Train und Test gleichen. Der zeitbasierte Test ist
härter: Die Ausfallquote im Test liegt mit 22,4 % über den 18,5 % im Training, und genau diese
Verschiebung muss ein Modell in der Praxis aushalten.

---

## Nach AP4 (Scorecard)

**Wie kommt man von einer PD zu einem Score-Punkt?**

Über die Odds. Aus der PD werden die Odds gut zu schlecht: (1 - PD) / PD. Der Score ist eine lineare
Funktion vom Logarithmus dieser Odds: Score = Offset + Factor x ln(Odds), mit Factor = PDO / ln(2) =
28,85 und Offset = 600 - 28,85 x ln(50) = 487,12. Beispiel aus meinem Test: PD 9,4 %, Odds 9,68, Score
487,12 + 28,85 x 2,27 = 552,6. Weil die logistische Regression die Log-Odds als Summe von Koeffizient
mal WoE berechnet, lässt sich der Score auf die Variablen verteilen: Jeder Bin bekommt feste Punkte,
und der Score ist ihre Summe. Beim selben Kredit gibt die Scorecard 552 Punkte.

**Dein AUC liegt bei 0,69 (Test) – ist das gut?**

Für Lending Club ohne die eigene Einstufung ja, das ist der typische Bereich von 0,68 bis 0,72. Wichtiger
als die Zahl ist, wie sie zustande kam: zeitlich getrennt getestet (2016 bis 2018 nach Training bis 2015),
ohne Leckage-Spalten, ohne grade und int_rate. Das Benchmark-Modell mit Lending Clubs grade und int_rate
kommt auf 0,705, also nur 0,017 mehr. Ein AUC von 0,90 wäre bei diesen Daten kein Erfolg, sondern ein
sicheres Zeichen, dass Information aus der Zukunft ins Modell gerutscht ist.

---

## Nach AP5 (Modellgüte)

**Warum logistische Regression statt Boosting, obwohl Boosting besser abschneidet?**

Das Boosting erreicht mit denselben 15 Variablen im Test 0,696 AUC gegen 0,688 der Scorecard, also
0,008 mehr. Dafür bekäme ich ein Modell mit 300 Bäumen, das weder ein Kunde bei einer Ablehnung noch
ein Prüfer nachvollziehen kann. Die Scorecard hat feste Punkte je Bin, ich kann jedes Vorzeichen und
jede Monotonie fachlich prüfen (zwei Variablen sind genau deshalb rausgeflogen), sie läuft in jedem
Kernbanksystem und lässt sich je Variable über die Zeit überwachen. BaFin und EBA verlangen
nachvollziehbare Modelle, und Kunden haben Anspruch auf eine Begründung. Das ist eine Abwägung, kein
Ausweichen: Wenn Boosting 0,05 mehr brächte, wäre die Diskussion eine andere.

**Was ist der Unterschied zwischen Trennschärfe und Kalibrierung, und welches ist hier wichtiger?**

Trennschärfe fragt: Ist Kunde A riskanter als Kunde B? Das misst der AUC. Kalibrierung fragt: Fallen
von 100 Kunden mit PD 10 % wirklich etwa 10 aus? Für die Expected-Loss-Rechnung ist Kalibrierung
wichtiger, weil EL = PD x LGD x EAD die PD direkt als Zahl benutzt. Ein Modell, das perfekt rangiert,
aber alle PDs halbiert, liefert die halbe Risikovorsorge. In meinem Repo ist das Modell auf dem
ausgereiften Training kalibriert (mittlere PD 18,45 % gegen 18,46 % beobachtet). Im Testzeitraum liegt
die beobachtete Quote 27 % über der PD, aber das ist der Zensierungseffekt: Von 2016 bis 2018 sind nur
die früh abgeschlossenen Kredite enthalten, und frühe Ausfälle sind darin überrepräsentiert. Den Effekt
muss man erkennen, sonst würde man das Modell fälschlich "nachkalibrieren".

**Was misst der PSI?**

Der Population Stability Index misst, ob sich die Verteilung des Scores (oder einer Variable) zwischen
zwei Zeiträumen verschoben hat. Man teilt die Referenz in zehn gleich große Bins, schaut, welcher
Anteil der neuen Daten in jeden Bin fällt, und summiert (Anteil neu minus Anteil alt) mal ln(Anteil neu
durch Anteil alt). Unter 0,10 gilt als stabil, über 0,25 als kritisch. Mein Score hat zwischen
2007–2015 und 2016–2018 einen PSI von 0,008, die Verteilung ist also praktisch gleich geblieben. Ein
hoher PSI wäre kein Fehler des Modells, sondern ein Hinweis, dass die Kunden anders geworden sind und
das Modell neu geprüft werden muss.

---

## Nach AP6 (Expected Loss)

**Erkläre EL = PD x LGD x EAD.**

Der erwartete Verlust eines Kredits ist die Wahrscheinlichkeit, dass er ausfällt (PD), mal dem Anteil
des Betrags, der bei einem Ausfall verloren geht (LGD), mal dem Betrag, der im Ausfallzeitpunkt
aussteht (EAD). Bei mir kommt die PD aus der Scorecard, die LGD ist empirisch 62,2 %, das EAD ist die
Auszahlung. Ein Kredit über 15.000 USD mit PD 10 % hat einen EL von 0,10 x 0,622 x 15.000 = 933 USD.
Über das Testportfolio summiert sind das 887 Mio. USD oder 11,83 % von 7,5 Mrd. USD Volumen. Wichtig:
Meine PD gilt für die gesamte Laufzeit, der EL ist also ein Lifetime-EL, nicht ein 12-Monats-Wert.

**Wie hast du die LGD geschätzt, und warum ist das hier ohne Leckage zulässig?**

Auf den 269.360 ausgefallenen Krediten als 1 minus (Rückflüsse nach Ausfall plus vor dem Ausfall
getilgter Betrag) geteilt durch die Auszahlung. Mittelwert 62,2 %, Median 66,4 %. Die Spalten
recoveries und total_rec_prncp sind Leckage-Spalten, weil sie erst nach der Kreditvergabe entstehen. Im
PD-Modell wären sie ein Fehler, denn dort will ich vorhersagen, ob ein Kredit ausfällt, und diese
Spalten verraten es. Bei der LGD frage ich etwas anderes: Wenn ein Kredit ausgefallen ist, wie viel ist
weg? Dafür schaue ich nur auf bereits ausgefallene Kredite, und dort ist der Ausfall keine Zukunft mehr,
sondern Vergangenheit. Deshalb liegen die Spalten in einer eigenen Datei, die das PD-Modell nie sieht.

**Unterschied zwischen regulatorischem EL und IFRS-9-ECL?**

Der regulatorische EL nach Basel dient der Eigenkapitalunterlegung: 12-Monats-Horizont, durch den
Zyklus, konservativ, teils mit aufsichtlich vorgegebenen Parametern (zum Beispiel die 45 % LGD im
Foundation-IRB für unbesicherte Forderungen an Unternehmen, die kein Retail-Wert sind). Der
IFRS-9-ECL dient der Risikovorsorge in der Bilanz: eigene, unverzerrte, zeitpunktbezogene und
zukunftsgerichtete Schätzung, mit Horizont 12 Monate in Stage 1 und Lifetime in Stage 2 und 3. Mein
Lifetime-EL mit empirischer LGD ist von der Logik her näher an einem Stage-2-ECL als an Basel.

**Wann wechselt ein Kredit von Stage 1 nach Stage 2?**

Bei einem signifikanten Anstieg des Kreditrisikos seit Vergabe (SICR), zum Beispiel wenn die PD
deutlich über den Wert bei Vergabe steigt oder ein Frühwarnsignal anschlägt. Es gibt eine widerlegbare
Vermutung, dass ab mehr als 30 Tagen Zahlungsverzug ein SICR vorliegt. Ab Stage 2 wird statt der
12-Monats-ECL die Lifetime-ECL gebucht. Stage 3 ist der Ausfall selbst, dann wird der Zins nur noch auf
Nettobasis vereinnahmt. Im Lending-Club-Datensatz wären die Status "Late (31-120 days)" typische
Stage-2-Kandidaten, "Charged Off" ist Stage 3.

---

## Nach AP7 (Cutoff)

**Wie würdest du den optimalen Cutoff bestimmen, wenn du die Marge kennst?**

Über den Break-even je Kredit: Ein Kredit lohnt sich, wenn die erwartete Marge größer ist als der
erwartete Verlust, also Marge > PD x LGD (beides in Prozent des Betrags). Bei LGD 62,2 % und einer
Marge von zum Beispiel 8 % über die Laufzeit ist die Grenz-PD 8 % / 0,622 = 12,9 %. Daraus folgt der
Cutoff direkt aus der Scorecard: PD 12,9 % entspricht Odds 6,8 und damit Score 487 + 28,85 x ln(6,8) =
542. Mit bekannter Marge kann ich den Cutoff also je Kredit begründen, statt den Knick der Kurve zu
nehmen. Mein Knick bei 515 ist deutlich lockerer, weil er nur den Verlauf der Verlustkurve nutzt, nicht
den Ertrag.

**Was kostet ein zu konservativer Cutoff?**

Volumen und gute Kunden. Bei Cutoff 540 statt 515 fällt die Annahmequote im Testportfolio von 84,5 %
auf 46,1 %, das genehmigte Volumen sinkt um 58 % statt 20 %, und man lehnt 48 % der Kredite ab, die
vollständig zurückgezahlt worden wären. Der EL des angenommenen Portfolios sinkt zwar von 8,80 % auf
5,51 %, aber die Zinseinnahmen der 38 Prozentpunkte zusätzlich abgelehnten Kredite fehlen komplett.
Ein zu strenger Cutoff ist also kein "sicher", sondern eine Entscheidung gegen Ertrag, und die Kurve
zeigt, dass jeder weitere Prozentpunkt EL-Senkung oberhalb von 515 überproportional Volumen kostet.

**Wie würde sich die Empfehlung ändern, wenn die LGD bei 60 % statt 40 % läge?**

Der EL jedes Kredits wäre um die Hälfte höher (Faktor 60/40 = 1,5). Weil ich eine LGD für alle
Kredite verwende, ändert das die Form der Kurve nicht, nur ihr Niveau: Der Knick bleibt bei 515, aber
jeder gesparte Prozentpunkt Volumen ist 1,5-mal so viel wert. In meiner Sensitivität steigt der am
Cutoff 515 gesparte EL von 174 Mio. USD (LGD 30 %) auf 348 Mio. USD (LGD 60 %). Mit dem
Break-even-Argument aus der ersten Frage würde der Cutoff bei höherer LGD strenger: Die Grenz-PD ist
Marge / LGD, sie sinkt von 20 % (Marge 8 %, LGD 40 %) auf 13,3 % (LGD 60 %). Höhere Verlustquote
heißt also weniger Spielraum bei der Annahme.

---

## Die 90-Sekunden-Story (mit den echten Zahlen dieses Repos)

> Banken müssen bei jedem Kredit entscheiden: annehmen oder ablehnen. Zu streng heißt Geschäft
> verlieren, zu locker heißt Verluste. Ich habe diese Entscheidung mit Daten unterlegt.
>
> Grundlage waren 2,26 Millionen echte US-Konsumentenkredite von Lending Club, davon 1,35 Millionen
> mit bekanntem Ausgang. Erster Schritt war Datenhygiene: Der Datensatz enthält 38 Spalten, die erst
> nach der Kreditvergabe entstehen, Rückzahlungen, Verwertungserlöse, Härtefallprogramme. Wer die
> einbaut, bekommt ein Modell, das im Test brilliert und in der Praxis wertlos ist. Die habe ich als
> explizite Liste im Code entfernt.
>
> Dann habe ich in SQL die Ausfallmuster analysiert, Vintage-Kurven pro Jahrgang gebaut, inklusive
> Reifegrad, weil junge Jahrgänge noch nicht ausgelaufen sind, und in Python eine klassische Scorecard
> mit Weight-of-Evidence-Binning und logistischer Regression trainiert. Zeitlich getrennt getestet,
> Training bis 2015, Test 2016 bis 2018. Gini 0,38, AUC 0,69, ohne Lending Clubs eigene Einstufung, die
> im Vergleich nur 0,017 AUC mehr bringt. Die PD ist auf dem ausgereiften Portfolio sauber kalibriert,
> und das ist hier wichtiger als reine Trennschärfe, weil sie direkt in die Verlustrechnung eingeht.
>
> Daraus habe ich den Expected Loss gerechnet, mit einer LGD von 62 %, die ich aus den tatsächlichen
> Rückflüssen von 269.000 ausgefallenen Krediten geschätzt statt geraten habe.
>
> Das Ergebnis ist ein Dashboard mit einem Cutoff-Regler: Ein Cutoff bei Score 515 senkt den erwarteten
> Verlust von 11,8 auf 8,8 Prozent des Volumens, also um ein Viertel, und kostet 20 Prozent des
> Neugeschäfts. Damit kann jemand ohne Statistikkenntnisse die Entscheidung selbst durchspielen.
>
> Gelernt habe ich vor allem, dass das Schwierigste an so einem Projekt nicht das Modell ist, sondern
> zu wissen, welche Information zum Entscheidungszeitpunkt überhaupt zur Verfügung stand.
