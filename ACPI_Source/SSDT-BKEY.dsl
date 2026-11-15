/*
 * ASUS Vivobook S16 S5650AA: Route Fn+F4/F5 brightness EC queries (_Q06/_Q07)
 * directly to VoodooPS2Keyboard via PS2K ACPI notifications (0x0405 / 0x0406 -> ADB 0x6b / 0x71).
 *
 * Requires OpenCore ACPI -> Patch renames in DSDT:
 *   H_EC._Q06 (5F513036 00) -> XQ06 (58513036 00)
 *   H_EC._Q07 (5F513037 00) -> XQ07 (58513037 00)
 */
DefinitionBlock ("", "SSDT", 2, "ASUS", "BKEY", 0x00000000)
{
    External (_SB_.PC00.LPCB.H_EC, DeviceObj)
    External (_SB_.PC00.LPCB.H_EC.XQ06, MethodObj)    // 0 Arguments
    External (_SB_.PC00.LPCB.H_EC.XQ07, MethodObj)    // 0 Arguments
    External (_SB_.PC00.PS2K, DeviceObj)

    Scope (\_SB.PC00.LPCB.H_EC)
    {
        Method (_Q06, 0, NotSerialized)  // Fn+F4 Brightness Down
        {
            If (_OSI ("Darwin"))
            {
                Notify (\_SB.PC00.PS2K, 0x0405)
            }
            Else
            {
                \_SB.PC00.LPCB.H_EC.XQ06 ()
            }
        }

        Method (_Q07, 0, NotSerialized)  // Fn+F5 Brightness Up
        {
            If (_OSI ("Darwin"))
            {
                Notify (\_SB.PC00.PS2K, 0x0406)
            }
            Else
            {
                \_SB.PC00.LPCB.H_EC.XQ07 ()
            }
        }
    }
}
