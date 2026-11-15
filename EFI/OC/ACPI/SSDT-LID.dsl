/*
 * ASUS Vivobook S16 S5650AA: Fix LID0._LID and EC lid queries (_Q0C/_Q0D) for macOS AppleACPILid.
 *
 * Firmware DSDT reads LSTE via ECRD(RefOf(LSTE)) while ECAV starts as 1 before H_EC._REG(3, 1),
 * and Apple's ACPICA fails/aborts on early EC access or DerefOf(RefOf(FieldUnit)), preventing
 * AppleACPILid from publishing AppleClamshellState on IOPMrootDomain.
 *
 * Requires OpenCore ACPI -> Patch renames in DSDT:
 *   H_EC._REG      (5F524547 02) -> XREG (58524547 02)
 *   H_EC._Q0C      (5F513043 00) -> XQ0C (58513043 00)
 *   H_EC._Q0D      (5F513044 00) -> XQ0D (58513044 00)
 *   H_EC.LID0._LID (5F4C4944 00) -> XLID (584C4944 00)
 */
DefinitionBlock ("", "SSDT", 2, "ASUS", "LIDFIX", 0x00000000)
{
    External (_SB_.PC00.LPCB.H_EC, DeviceObj)
    External (_SB_.PC00.LPCB.H_EC.LID0, DeviceObj)
    External (_SB_.PC00.LPCB.H_EC.LSTE, FieldUnitObj)
    External (_SB_.PC00.LPCB.H_EC.XREG, MethodObj)       // 2 Arguments
    External (_SB_.PC00.LPCB.H_EC.XQ0C, MethodObj)       // 0 Arguments
    External (_SB_.PC00.LPCB.H_EC.XQ0D, MethodObj)       // 0 Arguments
    External (_SB_.PC00.LPCB.H_EC.LID0.XLID, MethodObj)  // 0 Arguments
    External (_SB_.PC00.GFX0.CLID, FieldUnitObj)
    External (LIDS, FieldUnitObj)

    Scope (\_SB.PC00.LPCB.H_EC)
    {
        Name (ECRG, Zero)

        Method (_REG, 2, NotSerialized)  // _REG: Region Availability
        {
            If ((Arg0 == 0x03))
            {
                If ((Arg1 == One))
                {
                    ECRG = One
                }
                Else
                {
                    ECRG = Zero
                }
            }

            \_SB.PC00.LPCB.H_EC.XREG (Arg0, Arg1)

            If ((_OSI ("Darwin") && ((Arg0 == 0x03) && (Arg1 == One))))
            {
                Notify (\_SB.PC00.LPCB.H_EC.LID0, 0x80) // Status Change
            }
        }

        Method (_Q0C, 0, NotSerialized)  // Lid Close/Open EC Query
        {
            If (_OSI ("Darwin"))
            {
                LIDS = \_SB.PC00.LPCB.H_EC.LSTE
                If (CondRefOf (\_SB.PC00.GFX0.CLID))
                {
                    \_SB.PC00.GFX0.CLID = LIDS
                }

                Notify (\_SB.PC00.LPCB.H_EC.LID0, 0x80) // Status Change
            }
            Else
            {
                \_SB.PC00.LPCB.H_EC.XQ0C ()
            }
        }

        Method (_Q0D, 0, NotSerialized)  // Lid Close/Open EC Query
        {
            If (_OSI ("Darwin"))
            {
                LIDS = \_SB.PC00.LPCB.H_EC.LSTE
                If (CondRefOf (\_SB.PC00.GFX0.CLID))
                {
                    \_SB.PC00.GFX0.CLID = LIDS
                }

                Notify (\_SB.PC00.LPCB.H_EC.LID0, 0x80) // Status Change
            }
            Else
            {
                \_SB.PC00.LPCB.H_EC.XQ0D ()
            }
        }

        Scope (LID0)
        {
            Method (_LID, 0, NotSerialized)  // _LID: Lid Status
            {
                If (_OSI ("Darwin"))
                {
                    If (\_SB.PC00.LPCB.H_EC.ECRG)
                    {
                        Return (\_SB.PC00.LPCB.H_EC.LSTE)
                    }

                    Return (One)
                }
                Else
                {
                    Return (\_SB.PC00.LPCB.H_EC.LID0.XLID ())
                }
            }
        }
    }
}
