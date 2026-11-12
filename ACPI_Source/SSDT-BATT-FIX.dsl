DefinitionBlock ("", "SSDT", 2, "CORP", "BATFIX", 0x00000000)
{
    External (_SB_.PC00.LPCB.H_EC.BAT0, DeviceObj)
    External (_SB_.PC00.LPCB.H_EC.BAT0.XBIX, MethodObj)
    External (_SB_.PC00.LPCB.H_EC.B1FV, FieldUnitObj)

    Scope (\_SB.PC00.LPCB.H_EC.BAT0)
    {
        Method (_BIX, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                Local0 = \_SB.PC00.LPCB.H_EC.BAT0.XBIX ()
                If ((ObjectType (Local0) == 0x04))
                {
                    // Fix Power Unit to 1 (mWh, since capacity values are in mWh)
                    Local0 [One] = One
                    // Fix Design Voltage to B1FV (mV) instead of 0xFFFFFFFF
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
