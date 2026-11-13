DefinitionBlock ("", "SSDT", 2, "CORP", "BATFIX", 0x00000000)
{
    External (_SB_.PC00.LPCB.H_EC.BAT0, DeviceObj)
    External (_SB_.PC00.LPCB.H_EC.BAT0.XBIF, MethodObj)
    External (_SB_.PC00.LPCB.H_EC.BAT0.XBIX, MethodObj)
    External (_SB_.PC00.LPCB.H_EC.B1DC, FieldUnitObj)
    External (_SB_.PC00.LPCB.H_EC.B1FC, FieldUnitObj)
    External (_SB_.PC00.LPCB.H_EC.B1FV, FieldUnitObj)
    External (_SB_.PC00.LPCB.H_EC.BACC, FieldUnitObj)

    Scope (\_SB.PC00.LPCB.H_EC.BAT0)
    {
        Method (_BIF, 0, Serialized)
        {
            If (_OSI ("Darwin"))
            {
                Name (BPKG, Package (0x0D)
                {
                    Zero,
                    Zero,
                    Zero,
                    Zero,
                    Zero,
                    Zero,
                    Zero,
                    Zero,
                    Zero,
                    "SR Real Battery",
                    "123456789",
                    "Lion",
                    "Dongguan Ganfeng Electronics Co., Ltd."
                })

                // Design Capacity in mWh
                BPKG [One] = ((\_SB.PC00.LPCB.H_EC.B1DC * \_SB.PC00.LPCB.H_EC.B1FV) / 0x03E8)
                // Last Full Charge Capacity in mWh
                BPKG [0x02] = ((\_SB.PC00.LPCB.H_EC.B1FC * \_SB.PC00.LPCB.H_EC.B1FV) / 0x03E8)
                // Battery Technology: 1 = Rechargeable
                BPKG [0x03] = One
                // Design Voltage in mV (fixes ASUS bug where it returned 1 mV)
                BPKG [0x04] = \_SB.PC00.LPCB.H_EC.B1FV
                If (\_SB.PC00.LPCB.H_EC.B1FC)
                {
                    BPKG [0x05] = ((\_SB.PC00.LPCB.H_EC.B1FC * 0x0A) / 0x0A)
                    BPKG [0x06] = ((\_SB.PC00.LPCB.H_EC.B1FC * 0x0A) / 0x19)
                    BPKG [0x07] = ((\_SB.PC00.LPCB.H_EC.B1DC * 0x0A) / 0x64)
                }

                Return (BPKG)
            }
            Else
            {
                Return (\_SB.PC00.LPCB.H_EC.BAT0.XBIF ())
            }
        }

        Method (_BIX, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                Local0 = \_SB.PC00.LPCB.H_EC.BAT0.XBIX ()
                If ((ObjectType (Local0) == 0x04))
                {
                    // Power Unit: 0 = mWh
                    Local0 [One] = Zero
                    // Design Voltage: B1FV mV (fixes ASUS bug where it was 0xFFFFFFFF)
                    Local0 [0x05] = \_SB.PC00.LPCB.H_EC.B1FV
                    Return (Local0)
                }
                Return (Local0)
            }
            Else
            {
                Return (\_SB.PC00.LPCB.H_EC.BAT0.XBIX ())
            }
        }
    }
}
