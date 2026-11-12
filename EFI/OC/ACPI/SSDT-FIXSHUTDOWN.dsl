/*
 * Intel ACPI Component Architecture
 * AML/ASL+ Disassembler version 20260408 (32-bit version)
 * Copyright (c) 2000 - 2026 Intel Corporation
 * 
 * Disassembling to symbolic ASL+ operators
 *
 * Disassembly of C:/Users/yangy/.gemini/antigravity/scratch/ASUS-S5650AA-Hackintosh/EFI/OC/ACPI/SSDT-FIXSHUTDOWN.aml
 *
 * Original Table Header:
 *     Signature        "SSDT"
 *     Length           0x0000011A (282)
 *     Revision         0x02
 *     Checksum         0x8C
 *     OEM ID           "ASUS  "
 *     OEM Table ID     "FIXSHUT"
 *     OEM Revision     0x00000000 (0)
 *     Compiler ID      "INTL"
 *     Compiler Version 0x20260930 (539363632)
 */
DefinitionBlock ("", "SSDT", 2, "ASUS  ", "FIXSHUT", 0x00000000)
{
    External (_SB_.PC00.TXHC, DeviceObj)
    External (_SB_.PC00.TXHC._STA, MethodObj)    // 0 Arguments
    External (_SB_.PC00.TXHC.PMEE, FieldUnitObj)
    External (_SB_.PC00.XHCI.PMEE, FieldUnitObj)
    External (ZPTS, MethodObj)    // 1 Arguments

    Method (_PTS, 1, NotSerialized)  // _PTS: Prepare To Sleep
    {
        ZPTS (Arg0)
        If (_OSI ("Darwin"))
        {
            If ((0x05 == Arg0))
            {
                If (CondRefOf (\_SB.PC00.XHCI.PMEE))
                {
                    \_SB.PC00.XHCI.PMEE = Zero
                }

                If (CondRefOf (\_SB.PC00.TXHC.PMEE))
                {
                    If ((\_SB.PC00.TXHC._STA () & One))
                    {
                        \_SB.PC00.TXHC.PMEE = Zero
                    }
                }
            }
        }
    }
}

