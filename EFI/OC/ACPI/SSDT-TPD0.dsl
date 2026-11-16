/*
 * Intel ACPI Component Architecture
 * AML/ASL+ Disassembler version 20260408 (32-bit version)
 * Copyright (c) 2000 - 2026 Intel Corporation
 * 
 * Disassembling to symbolic ASL+ operators
 *
 * Disassembly of S:/EFI/OC/ACPI/SSDT-TPD0.aml
 *
 * Original Table Header:
 *     Signature        "SSDT"
 *     Length           0x0000009F (159)
 *     Revision         0x02
 *     Checksum         0xE6
 *     OEM ID           "CORP"
 *     OEM Table ID     "TPD0"
 *     OEM Revision     0x00000000 (0)
 *     Compiler ID      "INTL"
 *     Compiler Version 0x20260408 (539362312)
 */
DefinitionBlock ("", "SSDT", 2, "CORP", "TPD0", 0x00000000)
{
    External (_SB_.PC00.I2C0.TPD0, DeviceObj)
    External (_SB_.PC00.I2C0.TPD0.XSTA, MethodObj)    // 0 Arguments

    Scope (\_SB.PC00.I2C0.TPD0)
    {
        Method (_STA, 0, NotSerialized)  // _STA: Status
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

