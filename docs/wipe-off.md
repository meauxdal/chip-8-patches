# Wipe Off preservation fix

The common 206-byte image is identified in the CHIP-8 database by SHA-1
`d666688a8fce468a7d88b536bc1ef5f35ba12031`.
The fixed image has SHA-256
`3e5e87255c96369e41a16499b47229b973cfdfc2972d371f4a4f725e52c50412`.

The RCA COSMAC VIP manual gives `021E: 6714`, providing the documented 20
balls. The common functional image instead contains `6710`. The patch changes
only byte `021F` from `10` to `14`. This also reproduces the intact portion of
the TCNJ S.572.2 dump without retaining that dump's corrupt final-score tail.
