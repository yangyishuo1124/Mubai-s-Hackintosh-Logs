/*
 * ASUS Vivobook S16 S5650AA:
 * 1) Fix Camera (XHCI.RHUB.HS02, USB VID_3277&PID_0101):
 *    UpmpSsdt defines child devices WCAM (_ADR=2, _UPC[0]=0) and CIR (_ADR=4, _UPC[0]=0xFF)
 *    under HS02, hiding physical port 2 (HS02) in macOS and exposing bogus CIR@14300000 (port 4).
 *    - Disable WCAM and CIR under _OSI ("Darwin") (CIR uses OpenCore UpmpSsdt _STA -> XSTA rename).
 *    - Define \_SB.A2UP so HS02._UPC returns connectable internal USB (0xFF, 0xFF) under Darwin.
 * 2) Fix TCSS / Thunderbolt Type-C initialization after Windows boot:
 *    Windows switches TDM0 (8086:E333) to SW CM and stores it in CMOS 0xF2; macOS has no USB4 SW CM
 *    driver for TDM0, leaving Type-C/TBT firmware CM inactive and IOM entering RTD3 D3Cold.
 *    Under _OSI ("Darwin"), invoke \_SB.PC00.TDM0.CHCM (Zero) to switch to Firmware CM (FW CM) +
 *    Connect Topology, clear SCME/OSCM, and prevent TDM0 RTD3 D3Cold entry via SD3C=1.
 */
DefinitionBlock ("", "SSDT", 2, "ASUS", "USBFIX", 0x00000000)
{
    External (_SB_.OSCM, IntObj)
    External (_SB_.PC00, DeviceObj)
    External (_SB_.PC00.TDM0, DeviceObj)
    External (_SB_.PC00.TDM0._STA, MethodObj)    // 0 Arguments
    External (_SB_.PC00.TDM0.CHCM, MethodObj)    // 1 Arguments
    External (_SB_.PC00.TDM0.SCME, UnknownObj)
    External (_SB_.PC00.TDM0.SD3C, UnknownObj)
    External (_SB_.PC00.TDM0.VDID, FieldUnitObj)
    External (_SB_.PC00.XHCI.RHUB.HS02.WCAM, DeviceObj)
    External (_SB_.PC00.XHCI.RHUB.HS02.CIR, DeviceObj)
    External (_SB_.PC00.XHCI.RHUB.HS02.CIR.XSTA, MethodObj)    // 0 Arguments

    Scope (\_SB)
    {
        Method (A2UP, 0, Serialized)
        {
            If (_OSI ("Darwin"))
            {
                Return (Package (0x02)
                {
                    One,
                    Package (0x04)
                    {
                        0xFF,
                        0xFF,
                        Zero,
                        Zero
                    }
                })
            }

            Return (Package (0x02)
            {
                Zero,
                Package (0x04)
                {
                    Zero,
                    0xFF,
                    Zero,
                    Zero
                }
            })
        }
    }

    If (CondRefOf (\_SB.PC00.XHCI.RHUB.HS02.WCAM))
    {
        Scope (\_SB.PC00.XHCI.RHUB.HS02.WCAM)
        {
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin"))
                {
                    Return (Zero)
                }

                Return (0x0F)
            }
        }
    }

    If (CondRefOf (\_SB.PC00.XHCI.RHUB.HS02.CIR))
    {
        Scope (\_SB.PC00.XHCI.RHUB.HS02.CIR)
        {
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin"))
                {
                    Return (Zero)
                }

                If (CondRefOf (\_SB.PC00.XHCI.RHUB.HS02.CIR.XSTA))
                {
                    Return (\_SB.PC00.XHCI.RHUB.HS02.CIR.XSTA ())
                }

                Return (0x0F)
            }
        }
    }

    Scope (\_SB.PC00)
    {
        Device (TBFX)
        {
            Name (_HID, "ACID0002")
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }

                Return (Zero)
            }

            Method (_INI, 0, Serialized)
            {
                If (_OSI ("Darwin"))
                {
                    If ((CondRefOf (\_SB.PC00.TDM0._STA) && (\_SB.PC00.TDM0._STA () != Zero)))
                    {
                        If ((CondRefOf (\_SB.PC00.TDM0.VDID) && (\_SB.PC00.TDM0.VDID != 0xFFFFFFFF)))
                        {
                            If (CondRefOf (\_SB.PC00.TDM0.CHCM))
                            {
                                \_SB.PC00.TDM0.CHCM (Zero)
                            }

                            If (CondRefOf (\_SB.PC00.TDM0.SCME))
                            {
                                \_SB.PC00.TDM0.SCME = Zero
                            }

                            If (CondRefOf (\_SB.OSCM))
                            {
                                \_SB.OSCM = Zero
                            }

                            If (CondRefOf (\_SB.PC00.TDM0.SD3C))
                            {
                                \_SB.PC00.TDM0.SD3C = One
                            }
                        }
                    }
                }
            }
        }
    }
}
