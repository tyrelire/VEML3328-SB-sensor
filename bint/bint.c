#include <xc.h>

#define _XTAL_FREQ 4000000

#pragma config FOSC = INTOSC, WDTE = OFF, PWRTE = OFF, MCLRE = ON
#pragma config CP = OFF, CPD = OFF, BOREN = ON, CLKOUTEN = OFF
#pragma config IESO = OFF, FCMEN = OFF

#define RELAIS_K7 LATCbits.LATC0
#define RELAIS_K6 LATCbits.LATC1
#define RELAIS_K1 LATCbits.LATC6

#define ZONE_A LATCbits.LATC4
#define ZONE_B LATCbits.LATC5

#define RS_DE LATAbits.LATA1
#define RS_DI LATBbits.LATB7

#define BTN_STOP  PORTAbits.RA2
#define BTN_START PORTAbits.RA4
#define SWITCH_MODE PORTAbits.RA3

#define ADDR_CYCLE 0x00
#define ADDR_ETAPE 0x01

enum Etat { IDLE, CYCLE, PAUSE, VALIDATION_VISUELLE, TERMINE };
enum Etat etat = IDLE;

unsigned char cycle_en_cours = 0;
unsigned char etape_cycle = 0;

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

unsigned char eeprom_read(unsigned char addr) {
    EEADR = addr;
    EECON1bits.EEPGD = 0;
    EECON1bits.CFGS = 0;
    EECON1bits.RD = 1;
    return EEDATA;
}

void initGPIO() {
    TRISC = 0x00;
    LATC = 0x00;
    TRISAbits.TRISA2 = 1;
    ANSELAbits.ANSA2 = 0;
    TRISAbits.TRISA3 = 1;
    TRISAbits.TRISA4 = 1;
    ANSELAbits.ANSA4 = 0;
    TRISAbits.TRISA1 = 0;
    TRISBbits.TRISB7 = 0;
    OPTION_REGbits.nWPUEN = 0;
    WPUAbits.WPUA2 = 1;
    WPUAbits.WPUA3 = 1;
    WPUAbits.WPUA4 = 1;
}

void setLedVert()   { RELAIS_K1 = 1; RELAIS_K6 = 0; RELAIS_K7 = 0; }
void setLedRouge()  { RELAIS_K1 = 1; RELAIS_K6 = 1; RELAIS_K7 = 0; }
void setLedJaune()  { RELAIS_K1 = 1; RELAIS_K6 = 0; RELAIS_K7 = 1; }
void eteindreLeds() { RELAIS_K1 = 0; RELAIS_K6 = 0; RELAIS_K7 = 0; }

void allumerZoneA()   { ZONE_A = 1; ZONE_B = 0; }
void allumerZoneB()   { ZONE_A = 0; ZONE_B = 1; }
void eteindreZones()  { ZONE_A = 0; ZONE_B = 0; }

void envoyerUART(unsigned char c) {
    while (!TXSTAbits.TRMT);
    TXREG = c;
}

void envoyerCommandeRS485(unsigned long data) {
    RS_DE = 1;
    envoyerUART((data >> 24) & 0xFF);
    envoyerUART((data >> 16) & 0xFF);
    envoyerUART((data >> 8) & 0xFF);
    envoyerUART(data & 0xFF);
    __delay_ms(1);
    RS_DE = 0;
}


char detecterAppui(char (*lectureBtn)(void)) {
    if (lectureBtn() == 0) {
        __delay_ms(20);
        if (lectureBtn() == 0) {
            while (lectureBtn() == 0);
            __delay_ms(20);
            return 1;
        }
    }
    return 0;
}

char lireBtnStart() { return BTN_START; }

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
        while (BTN_STOP == 0) {
            __delay_ms(500);
            maintien++;
            if (maintien >= 10) {
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

char attendreEtVerifierStop(unsigned int secondes) {
    for (unsigned int i = 0; i < secondes * 20; i++) {
        __delay_ms(50);
         envoyerCommandeRS485(0xFFFFFFFF);
        // envoyerCommandeRS485(0xAAAAAAAA);

        if (BTN_STOP == 0) {
            __delay_ms(30);
            if (BTN_STOP == 0) {
                unsigned int maintien = 0;
                while (BTN_STOP == 0) {
                    __delay_ms(500);
                    maintien++;
                    if (maintien >= 10) {
                        cycle_en_cours = 0;
                        etape_cycle = 0;
                        eeprom_write(ADDR_CYCLE, 10);
                        eeprom_write(ADDR_ETAPE, 0);
                        etat = IDLE;
                        return 1;
                    }
                }
                __delay_ms(30);
                eeprom_write(ADDR_CYCLE, cycle_en_cours);
                eeprom_write(ADDR_ETAPE, etape_cycle);
                etat = PAUSE;
                return 1;
            }
        }
    }
    return 0;
}

void clignoterLedVerte() {
    setLedVert();
    __delay_ms(500);
    eteindreLeds();
    __delay_ms(500);
}

void modeCycle() {
    setLedRouge();
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
    eeprom_write(ADDR_CYCLE, 10);
    etat = TERMINE;
}

void modeValidationVisuelle() {
    unsigned long couleurs[] = {
        0x00000000, 0xFF000000, 0x00FF0000,
        0x0000FF00, 0x000000FF, 0xFF000000
    };
    unsigned int inactivite = 0;
    allumerZoneA();
    while (inactivite < 3000) {
        for (int i = 0; i < 6; i++) {
            envoyerCommandeRS485(couleurs[i]);
            unsigned int d = (i == 0) ? 60 : 20;
            for (int t = 0; t < d; t++) {
                __delay_ms(100);
                inactivite++;
                if (detecterAppui(lireBtnStart)) {
                    allumerZoneB();
                    inactivite = 0;
                    break;
                }
                if (BTN_STOP == 0) {
                    envoyerCommandeRS485(0x00000000);
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

void initUART() {
    TXSTAbits.BRGH = 1;
    BAUDCONbits.BRG16 = 1;
    SPBRG = 103;
    SPBRGH = 0;
    TXSTAbits.SYNC = 0;
    RCSTAbits.SPEN = 1;
    TXSTAbits.TXEN = 1;
}

void main(void) {
    OSCCONbits.IRCF = 0b1101;
    OSCCONbits.SCS = 0b10;
    initGPIO();
    initUART();    

    while (1) {
        switch (etat) {
            case IDLE:
                setLedVert();
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
                modeCycle();
                break;
            case PAUSE:
                entrerPause();
                break;
            case TERMINE:
                clignoterLedVerte();
                if (detecterAppui(lireBtnStart)) etat = VALIDATION_VISUELLE;
                break;
            case VALIDATION_VISUELLE:
                modeValidationVisuelle();
                break;
            default:
                etat = IDLE;
                break;
        }
    }
}
