// === Configuration et définitions ===
#include <xc.h>

#define _XTAL_FREQ 4000000 // Fréquence d'oscillateur pour les délais

// Configuration des bits du microcontrôleur
#pragma config FOSC = INTOSC, WDTE = OFF, PWRTE = OFF, MCLRE = ON
#pragma config CP = OFF, CPD = OFF, BOREN = ON, CLKOUTEN = OFF
#pragma config IESO = OFF, FCMEN = OFF

// === Définition des relais et zones ===
#define RELAIS_K7 LATCbits.LATC0 // LED jaune
#define RELAIS_K6 LATCbits.LATC1 // LED rouge
#define RELAIS_K1 LATCbits.LATC6 // LED verte

#define ZONE_A LATCbits.LATC4    // Zone A projecteur
#define ZONE_B LATCbits.LATC5    // Zone B projecteur

// === Définition RS485 ===
#define RS_DE LATAbits.LATA1     // Driver Enable
#define RS_DI LATBbits.LATB7     // Driver Input

// === Boutons physiques ===
#define BTN_STOP  PORTAbits.RA2  // Bouton d'arrêt
#define BTN_START PORTAbits.RA4  // Bouton de démarrage
#define SWITCH_MODE PORTAbits.RA3 // Switch mode validation visuelle

// === Adresses EEPROM ===
#define ADDR_CYCLE 0x00 // Adresse sauvegarde cycle
#define ADDR_ETAPE 0x01 // Adresse sauvegarde étape

// === États du programme principal ===
enum Etat { IDLE, CYCLE, PAUSE, VALIDATION_VISUELLE, TERMINE };
enum Etat etat = IDLE; // État courant

unsigned char cycle_en_cours = 0; // Compteur de cycles
unsigned char etape_cycle = 0;    // Étape courante du cycle

// === Fonctions EEPROM ===
// Sauvegarde une valeur à une adresse donnée
void eeprom_write(unsigned char addr, unsigned char data) {
    EEADR = addr;
    EEDATA = data;
    EECON1bits.EEPGD = 0;
    EECON1bits.CFGS = 0;
    EECON1bits.WREN = 1;
    INTCONbits.GIE = 0;
    EECON2 = 0x55;
    EECON2 = 0xAA;
    EECON1bits.WR = 1;
    while (EECON1bits.WR);
    EECON1bits.WREN = 0;
    INTCONbits.GIE = 1;
}

// Lit une valeur à une adresse donnée
unsigned char eeprom_read(unsigned char addr) {
    EEADR = addr;
    EECON1bits.EEPGD = 0;
    EECON1bits.CFGS = 0;
    EECON1bits.RD = 1;
    return EEDATA;
}

// === Initialisation des GPIO ===
void initGPIO() {
    TRISC = 0x00;      // Tous les ports C en sortie
    LATC = 0x00;       // État initial bas
    TRISAbits.TRISA2 = 1; // RA2 en entrée (BTN_STOP)
    ANSELAbits.ANSA2 = 0; // RA2 en digital
    TRISAbits.TRISA3 = 1; // RA3 en entrée (SWITCH_MODE)
    TRISAbits.TRISA4 = 1; // RA4 en entrée (BTN_START)
    ANSELAbits.ANSA4 = 0; // RA4 en digital
    TRISAbits.TRISA1 = 0; // RA1 en sortie (RS_DE)
    TRISBbits.TRISB7 = 0; // RB7 en sortie (RS_DI)
    OPTION_REGbits.nWPUEN = 0; // Active les pull-up
    WPUAbits.WPUA2 = 1;   // Pull-up sur RA2
    WPUAbits.WPUA3 = 1;   // Pull-up sur RA3
    WPUAbits.WPUA4 = 1;   // Pull-up sur RA4
}

// === Contrôle des LEDs ===
void setLedVert()   { RELAIS_K1 = 1; RELAIS_K6 = 0; RELAIS_K7 = 0; } // LED verte
void setLedRouge()  { RELAIS_K1 = 1; RELAIS_K6 = 1; RELAIS_K7 = 0; } // LED rouge
void setLedJaune()  { RELAIS_K1 = 1; RELAIS_K6 = 0; RELAIS_K7 = 1; } // LED jaune
void eteindreLeds() { RELAIS_K1 = 0; RELAIS_K6 = 0; RELAIS_K7 = 0; } // Toutes LEDs éteintes

// === Contrôle des zones projecteur ===
void allumerZoneA()   { ZONE_A = 1; ZONE_B = 0; } // Active zone A
void allumerZoneB()   { ZONE_A = 0; ZONE_B = 1; } // Active zone B
void eteindreZones()  { ZONE_A = 0; ZONE_B = 0; } // Désactive toutes les zones

// === Communication UART ===
// Envoie un octet sur l'UART
void envoyerUART(unsigned char c) {
    while (!TXSTAbits.TRMT); // Attend que le buffer soit prêt
    TXREG = c;
}

// Envoie une commande 32 bits sur RS485 (4 octets)
void envoyerCommandeRS485(unsigned long data) {
    RS_DE = 1; // Active le driver
    envoyerUART((data >> 24) & 0xFF);
    envoyerUART((data >> 16) & 0xFF);
    envoyerUART((data >> 8) & 0xFF);
    envoyerUART(data & 0xFF);
    __delay_ms(1);
    RS_DE = 0; // Désactive le driver
}

// === Détection d'appui sur bouton ===
// Détecte un appui court sur un bouton (anti-rebond)
char detecterAppui(char (*lectureBtn)(void)) {
    if (lectureBtn() == 0) {
        __delay_ms(20); // Anti-rebond
        if (lectureBtn() == 0) {
            while (lectureBtn() == 0); // Attend relâchement
            __delay_ms(20);
            return 1;
        }
    }
    return 0;
}

// Lecture du bouton START
char lireBtnStart() { return BTN_START; }

// === Gestion de la pause ===
// Met le système en pause, clignote LED jaune, attend START ou arrêt prolongé
void entrerPause() {
    eteindreZones();
    while (1) {
        setLedJaune();
        __delay_ms(250);
        eteindreLeds();
        __delay_ms(250);
        if (detecterAppui(lireBtnStart)) {
            etat = CYCLE;
            return;
        }
        unsigned int maintien = 0;
        while (BTN_STOP == 0) { // Si bouton STOP maintenu
            __delay_ms(500);
            maintien++;
            if (maintien >= 10) { // Arrêt prolongé : reset cycle
                cycle_en_cours = 0;
                etape_cycle = 0;
                eeprom_write(ADDR_CYCLE, 10);
                eeprom_write(ADDR_ETAPE, 0);
                etat = IDLE;
                return;
            }
        }
    }
}

// Attend un certain temps ou un appui sur STOP, gère la sauvegarde d'état
char attendreEtVerifierStop(unsigned int secondes) {
    for (unsigned int i = 0; i < secondes * 20; i++) {
        __delay_ms(50);
        envoyerCommandeRS485(0xFFFFFFFF); // Commande de présence

        if (BTN_STOP == 0) { // Si STOP appuyé
            __delay_ms(30);
            if (BTN_STOP == 0) {
                unsigned int maintien = 0;
                while (BTN_STOP == 0) {
                    __delay_ms(500);
                    maintien++;
                    if (maintien >= 10) { // Arrêt prolongé : reset cycle
                        cycle_en_cours = 0;
                        etape_cycle = 0;
                        eeprom_write(ADDR_CYCLE, 10);
                        eeprom_write(ADDR_ETAPE, 0);
                        etat = IDLE;
                        return 1;
                    }
                }
                __delay_ms(30);
                eeprom_write(ADDR_CYCLE, cycle_en_cours); // Sauvegarde cycle
                eeprom_write(ADDR_ETAPE, etape_cycle);    // Sauvegarde étape
                etat = PAUSE;
                return 1;
            }
        }
    }
    return 0;
}

// Clignote la LED verte pour signaler la fin
void clignoterLedVerte() {
    setLedVert();
    __delay_ms(500);
    eteindreLeds();
    __delay_ms(500);
}

// === Mode cycle automatique ===
// Gère la séquence de test automatique
void modeCycle() {
    setLedRouge(); // Indique le début du cycle
    for (; cycle_en_cours < 10; cycle_en_cours++) {
        if (etape_cycle <= 0) {
            allumerZoneA();
            if (attendreEtVerifierStop(600)) return;
            etape_cycle++;
        }
        if (etape_cycle <= 1) {
            allumerZoneB();
            if (attendreEtVerifierStop(600)) return;
            etape_cycle++;
        }
        if (etape_cycle <= 2) {
            eteindreZones();
            if (attendreEtVerifierStop(600)) return;
            etape_cycle = 0;
        }
    }
    eteindreZones();
    cycle_en_cours = 0;
    etape_cycle = 0;
    eeprom_write(ADDR_CYCLE, 10); // Marque la fin du cycle
    etat = TERMINE;
}

// === Mode validation visuelle ===
// Permet de tester manuellement les couleurs via RS485
void modeValidationVisuelle() {
    unsigned long couleurs[] = {
        0x00000000, 0xFF000000, 0x00FF0000,
        0x0000FF00, 0x000000FF, 0xFF000000
    };
    unsigned int inactivite = 0;
    allumerZoneA();
    while (inactivite < 3000) {
        for (int i = 0; i < 6; i++) {
            envoyerCommandeRS485(couleurs[i]); // Envoie couleur
            unsigned int d = (i == 0) ? 60 : 20;
            for (int t = 0; t < d; t++) {
                __delay_ms(100);
                inactivite++;
                if (detecterAppui(lireBtnStart)) {
                    allumerZoneB(); // Passage à zone B
                    inactivite = 0;
                    break;
                }
                if (BTN_STOP == 0) {
                    envoyerCommandeRS485(0x00000000); // Éteint
                    while (BTN_STOP == 0);
                    inactivite = 0;
                    break;
                }
            }
        }
        setLedJaune();
        __delay_ms(500);
        eteindreLeds();
        __delay_ms(500);
    }
    eteindreZones();
    etat = IDLE;
}

// === Initialisation UART ===
void initUART() {
    TXSTAbits.BRGH = 1;      // High speed
    BAUDCONbits.BRG16 = 1;  // 16-bit baud rate
    SPBRG = 103;            // Baud rate 9600
    SPBRGH = 0;
    TXSTAbits.SYNC = 0;     // Mode asynchrone
    RCSTAbits.SPEN = 1;     // Active UART
    TXSTAbits.TXEN = 1;     // Active transmission
}

// === Point d'entrée principal ===
void main(void) {
    OSCCONbits.IRCF = 0b1101; // Oscillateur interne 4 MHz
    OSCCONbits.SCS = 0b10;    // Sélection source d'horloge
    initGPIO();               // Initialisation des entrées/sorties
    initUART();               // Initialisation UART    

    while (1) {
        switch (etat) {
            case IDLE:
                setLedVert(); // Attente
                if (detecterAppui(lireBtnStart)) {
                    unsigned char savedCycle = eeprom_read(ADDR_CYCLE);
                    if (savedCycle < 10) {
                        cycle_en_cours = savedCycle;
                        etape_cycle = eeprom_read(ADDR_ETAPE);
                        etat = CYCLE;
                    } else if (SWITCH_MODE == 1) {
                        etat = VALIDATION_VISUELLE;
                    } else {
                        etat = CYCLE;
                    }
                }
                break;
            case CYCLE:
                modeCycle(); // Lance le cycle automatique
                break;
            case PAUSE:
                entrerPause(); // Pause utilisateur
                break;
            case TERMINE:
                clignoterLedVerte(); // Fin de cycle
                if (detecterAppui(lireBtnStart)) etat = VALIDATION_VISUELLE;
                break;
            case VALIDATION_VISUELLE:
                modeValidationVisuelle(); // Mode manuel
                break;
            default:
                etat = IDLE;
                break;
        }
    }
}
