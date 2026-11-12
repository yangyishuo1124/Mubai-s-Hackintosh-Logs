DefinitionBlock ("", "SSDT", 2, "CORP", "TPD0", 0x00000000)
{
    External (_SB_.PC00.I2C0.TPD0, DeviceObj)
    External (_SB_.PC00.I2C0.TPD0.XSTA, MethodObj)

    Scope (\_SB.PC00.I2C0.TPD0)
    {
        Method (_STA, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                Return (0x0F)
            }
            Else
            {
                Return (\_SB.PC00.I2C0.TPD0.XSTA ())
            }
        }
    }
}
