DefinitionBlock ("", "SSDT", 2, "MUBAI", "PTLGPIO", 0x00000001)
{
    External (\TPDI, PkgObj)
    External (\_SB.G_IN, MethodObj)
    External (\_SB.GPI0, DeviceObj)
    External (\_SB.GPI1, DeviceObj)
    External (\_SB.GPI3, DeviceObj)
    External (\_SB.GPI4, DeviceObj)
    External (\_SB.GPI5, DeviceObj)
    Scope (\_SB.GPI0)
    {
        Method (PTIR, 0, Serialized)
        {
            Return (\TPDI)
        }
        Method (PTGR, 0, Serialized)
        {
            Return (\_SB.G_IN (DerefOf (\TPDI [Zero]), Zero, One, 0x02, Zero, Zero))
        }
    }
    External (\_SB.GPI1.GPPF, PkgObj)
    External (\_SB.GPI1.GPPE, PkgObj)
    Scope (\_SB.GPI1)
    {
        Method (PTG0, 0, Serialized) { Return (GPPF) }
        Method (PTG1, 0, Serialized) { Return (GPPE) }
        Method (PTIR, 0, Serialized)
        {
            Return (\TPDI)
        }
        Method (PTGR, 0, Serialized)
        {
            Return (\_SB.G_IN (DerefOf (\TPDI [Zero]), Zero, One, 0x02, Zero, Zero))
        }
    }
    Scope (\_SB.GPI3)
    {
        Method (PTIR, 0, Serialized)
        {
            Return (\TPDI)
        }
        Method (PTGR, 0, Serialized)
        {
            Return (\_SB.G_IN (DerefOf (\TPDI [Zero]), Zero, One, 0x02, Zero, Zero))
        }
    }
    Scope (\_SB.GPI4)
    {
        Method (PTIR, 0, Serialized)
        {
            Return (\TPDI)
        }
        Method (PTGR, 0, Serialized)
        {
            Return (\_SB.G_IN (DerefOf (\TPDI [Zero]), Zero, One, 0x02, Zero, Zero))
        }
    }
    Scope (\_SB.GPI5)
    {
        Method (PTIR, 0, Serialized)
        {
            Return (\TPDI)
        }
        Method (PTGR, 0, Serialized)
        {
            Return (\_SB.G_IN (DerefOf (\TPDI [Zero]), Zero, One, 0x02, Zero, Zero))
        }
    }
}
