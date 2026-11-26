#!/usr/bin/env python3
"""Automated verification suite for Loom-Pico compiler, BSP, ELF/UF2, and workspace-local libraries."""

import subprocess
import tempfile
import unittest
from pathlib import Path

PICO_ROOT = Path(__file__).resolve().parent.parent
LOOMC_RP2040 = PICO_ROOT / "build" / "loomc-rp2040"
BSP_DIR = PICO_ROOT / "sdk" / "targets" / "rp2040" / "bsp"
STD_DIR = PICO_ROOT / "sdk" / "std"
BLINKY_DIR = PICO_ROOT / "examples" / "Blinky_USB"
CONCURRENT_BLINKY_DIR = PICO_ROOT / "examples" / "Concurrent_Blinky"


class LoomPicoTests(unittest.TestCase):
    def test_all_bsp_modules_check(self):
        modules = list(BSP_DIR.glob("*.loom")) + list(STD_DIR.glob("*.loom"))
        self.assertGreaterEqual(len(modules), 17)
        for mod in modules:
            res = subprocess.run(
                [str(LOOMC_RP2040), "--check", str(mod), "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"{mod.name} failed:\n{res.stderr}")

    def test_baremetal_rejects_heap_threads_file_net(self):
        disallowed = [
            ("Allocate", "Block Main Declares\n P : Signed_32 Pointer\nImplements\n P = Allocate(4)\nEnd Main\n"),
            ("Open_File", "Block Main Declares\n F : File_Handle\nImplements\n F = Open_File(\"a.txt\", \"r\")\nEnd Main\n"),
            ("Tcp_Listen", "Block Main Declares\n Fd : Signed_32\nImplements\n Fd = Tcp_Listen(\"127.0.0.1\", 8080)\nEnd Main\n"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for name, src in disallowed:
                p = Path(tmp) / f"{name}.loom"
                p.write_text(f"Module TestReject\n{src}")
                res = subprocess.run([str(LOOMC_RP2040), "--check", str(p)], capture_output=True, text=True)
                self.assertNotEqual(res.returncode, 0, f"{name} should have been rejected on RP2040 bare-metal")

    def test_blinky_usb_elf_and_uf2_build(self):
        res = subprocess.run(
            ["loom", "build", "--toolchain", "rp2040", "--no-cache", "--verbose"],
            cwd=str(BLINKY_DIR), capture_output=True, text=True
        )
        self.assertEqual(res.returncode, 0, f"Blinky_USB build failed:\n{res.stdout}\n{res.stderr}")

        elf = BLINKY_DIR / "target" / "Blinky_USB.elf"
        uf2 = BLINKY_DIR / "target" / "Blinky_USB.uf2"
        self.assertTrue(elf.is_file(), "Missing Blinky_USB.elf")
        self.assertTrue(uf2.is_file(), "Missing Blinky_USB.uf2")

        objdump = subprocess.run(["arm-none-eabi-objdump", "-h", str(elf)], capture_output=True, text=True)
        self.assertEqual(objdump.returncode, 0, objdump.stderr)
        self.assertIn(".boot2", objdump.stdout)
        self.assertIn("00000100  10000000", objdump.stdout, f"Unexpected .boot2 section:\n{objdump.stdout}")
        self.assertIn(".vectors", objdump.stdout)
        self.assertIn(".text", objdump.stdout)

        pico = subprocess.run(["picotool", "info", "-a", str(uf2)], capture_output=True, text=True)
        self.assertEqual(pico.returncode, 0, f"picotool failed:\n{pico.stderr}")
        self.assertIn("0xe48ff566", pico.stdout)

    def test_concurrent_blinky_elf_and_uf2_build(self):
        res = subprocess.run(
            ["loom", "build", "--toolchain", "rp2040", "--no-cache", "--verbose"],
            cwd=str(CONCURRENT_BLINKY_DIR), capture_output=True, text=True
        )
        self.assertEqual(res.returncode, 0, f"Concurrent_Blinky build failed:\n{res.stdout}\n{res.stderr}")

        elf = CONCURRENT_BLINKY_DIR / "target" / "Concurrent_Blinky.elf"
        uf2 = CONCURRENT_BLINKY_DIR / "target" / "Concurrent_Blinky.uf2"
        self.assertTrue(elf.is_file(), "Missing Concurrent_Blinky.elf")
        self.assertTrue(uf2.is_file(), "Missing Concurrent_Blinky.uf2")

        objdump = subprocess.run(["arm-none-eabi-objdump", "-h", str(elf)], capture_output=True, text=True)
        self.assertEqual(objdump.returncode, 0, objdump.stderr)
        self.assertIn(".boot2", objdump.stdout)
        self.assertIn("00000100  10000000", objdump.stdout)
        self.assertIn(".vectors", objdump.stdout)
        self.assertIn(".text", objdump.stdout)
        self.assertIn(".bss", objdump.stdout)

        pico = subprocess.run(["picotool", "info", "-a", str(uf2)], capture_output=True, text=True)
        self.assertEqual(pico.returncode, 0, f"picotool failed:\n{pico.stderr}")
        self.assertIn("0xe48ff566", pico.stdout)

    def test_no_rtos_naming_in_bsp_or_examples(self):
        # Ensure 'rtos' (case-insensitive) does not appear in any BSP file or example source
        bsp_files = list(BSP_DIR.glob("*.loom"))
        example_files = list(CONCURRENT_BLINKY_DIR.glob("**/*.loom"))
        for path in bsp_files + example_files:
            content = path.read_text()
            self.assertNotIn("rtos", content.lower(), f"Forbidden word 'rtos' found in {path}")

    def test_zero_import_baremetal_spawn(self):
        # A Loom baremetal module with zero imports should successfully compile with Spawn, Gpio, Sync, and Thread
        src = r"""Module ZeroImportTest
Block Worker
Implements
    Loop
        Thread.Yield()
    End Loop
End Worker

Block Main
Declares
    LED_PIN : Constant Gpio.Pin = 25
    Lock : Sync.Mutex
Implements
    Lock.Init()
    Gpio.Init_Output(LED_PIN)
    Spawn Worker()
    Loop
        Lock.Acquire()
        LED_PIN.Toggle()
        Lock.Unlock()
        Thread.Yield()
    End Loop
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "zero_import.loom"
            obj = Path(tmp) / "zero_import.o"
            p.write_text(src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"Zero-import compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

    def test_channel_concurrency(self):
        # Baremetal channel communication between tasks
        src = r"""Module ChannelTest
Block Global
Declares
    Chan : Sync.Channel
End Global

Block Producer
Declares
    Val : Unsigned_32 = 42
Implements
    Chan.Send(Val)
End Producer

Block Consumer
Declares
    Received : Unsigned_32 = 0
Implements
    Received = Chan.Receive()
End Consumer

Block Main
Implements
    Chan.Init(8)
    Spawn Producer()
    Spawn Consumer()
    Loop
        Thread.Yield()
    End Loop
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "channel_test.loom"
            obj = Path(tmp) / "channel_test.o"
            p.write_text(src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"Channel concurrency compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

    def test_inline_assembly_and_intrinsics(self):
        # Native inline Asm block and Cortex-M0+ barrier intrinsics
        src = r"""Module AsmTest
Block Main
Implements
    System.NOP()
    System.DMB()
    Asm
        "wfe"
        "sev"
        "nop"
    End Asm
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "asm_test.loom"
            obj = Path(tmp) / "asm_test.o"
            p.write_text(src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"Inline assembly compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

            # Verify disassembled object contains the instructions
            dis = subprocess.run(["arm-none-eabi-objdump", "-d", str(obj)], capture_output=True, text=True)
            self.assertEqual(dis.returncode, 0)
            self.assertIn("wfe", dis.stdout)
            self.assertIn("sev", dis.stdout)
            self.assertIn("nop", dis.stdout)

    def test_multicore_spawn_on_core(self):
        # First-class 'Spawn Task() On Core'
        src = r"""Module SpawnCoreTest
Block Worker_0
Implements
    Loop
        Thread.Yield()
    End Loop
End Worker_0

Block Worker_1
Implements
    Loop
        Thread.Yield()
    End Loop
End Worker_1

Block Main
Implements
    Spawn Worker_0() On Thread.Core.Core0
    Spawn Worker_1() On Thread.Core.Core1
    Loop
        Thread.Yield()
    End Loop
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "spawn_core.loom"
            obj = Path(tmp) / "spawn_core.o"
            p.write_text(src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"Spawn on core compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

            # Verify call to loom_task_spawn_on_core in symbol table
            syms = subprocess.run(["arm-none-eabi-nm", str(obj)], capture_output=True, text=True)
            self.assertEqual(syms.returncode, 0)
            self.assertIn("loom_task_spawn_on_core", syms.stdout)

    def test_output_sink_routing(self):
        # Print redirection to UART / USB / Null
        src = r"""Module SinkTest
Block Main
Implements
    Usb_Cdc.Set_Output_Sink(Usb_Cdc.Output_Sink.UART0)
    Print("Routed to UART0\n")
    Usb_Cdc.Set_Output_Sink(Usb_Cdc.Output_Sink.USB)
    Print("Routed to USB CDC\n")
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sink_test.loom"
            obj = Path(tmp) / "sink_test.o"
            p.write_text(src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"Output sink routing compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

    def test_isr_block_codegen(self):
        # Hardware ISR routine with Cortex-M0+ interrupt calling convention
        src = r"""Module IsrTest
Block Gpio_Irq_Handler Interrupt
Implements
    System.NOP()
End Gpio_Irq_Handler

Block Main
Implements
    System.NOP()
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "isr_test.loom"
            obj = Path(tmp) / "isr_test.o"
            p.write_text(src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"ISR block compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

            # Verify disassembled object contains Gpio_Irq_Handler and bx lr exception return
            dis = subprocess.run(["arm-none-eabi-objdump", "-d", str(obj)], capture_output=True, text=True)
            self.assertEqual(dis.returncode, 0)
            self.assertIn("Gpio_Irq_Handler", dis.stdout)
            self.assertIn("bx\tlr", dis.stdout)

    def test_typestate_pin_conflict_detection(self):
        # Verification that conflicting peripheral pin assignments fail at compile-time
        conflict_src = r"""Module PinConflictTest
Block Main
Declares
    Pin_SDA : Constant Gpio.Pin = 4
    Pin_SCL : Constant Gpio.Pin = 5
Implements
    I2c.Init(I2c.I2c_Port.I2C0, Pin_SDA, Pin_SCL, 400000)
    # Attempting to re-claim Pin 4 as SPI without deinitializing I2C first:
    Spi.Init(Spi.Spi_Port.SPI0, 4, 17, 18, 19, 1000000)
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "pin_conflict.loom"
            obj = Path(tmp) / "pin_conflict.o"
            p.write_text(conflict_src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertNotEqual(res.returncode, 0, "Conflicting peripheral pin usage must be rejected at compile time")
            self.assertIn("pin conflict", res.stderr.lower())

    def test_pio_dsl_assembly(self):
        # Verification of first-class PIO DSL assembling directly to 16-bit instructions
        pio_src = r"""Module PioDslTest

Pio_Program Blink
Side_Set 1 Opt
Implements
    .Wrap_Target
    Set Pins, 1   Side 1 [4]
    Set Pins, 0   Side 0 [4]
    .Wrap
End Blink

Block Main
Declares
    Prog : Pio_Program
    Instr0 : Unsigned_16
    Instr1 : Unsigned_16
Implements
    Prog = Blink_Program()
    Instr0 = Blink_Instructions[1]
    Instr1 = Blink_Instructions[2]
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "pio_test.loom"
            obj = Path(tmp) / "pio_test.o"
            p.write_text(pio_src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"PIO DSL compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

            # Verify symbols generated for PIO program
            nm = subprocess.run(["arm-none-eabi-nm", str(obj)], capture_output=True, text=True)
            self.assertEqual(nm.returncode, 0)
            self.assertIn("Blink_Instructions", nm.stdout)
            self.assertIn("Blink_Program", nm.stdout)
            self.assertIn("Blink_Load", nm.stdout)

            # Verify actual assembled 16-bit opcodes in .rodata
            dump = subprocess.run(["arm-none-eabi-objdump", "-s", "-j", ".rodata.piodsltest__Blink_Instructions", str(obj)], capture_output=True, text=True)
            self.assertEqual(dump.returncode, 0)
            self.assertIn("01fc00f4", dump.stdout)

        # Also verify multi-instruction PIO assembly with labels and conditionals (WS2812)
        ws2812_src = r"""Module PioWs2812Test

Pio_Program Ws2812
Side_Set 1 Opt
Implements
    .Wrap_Target
    Bitloop:
        Out X, 1 Side 0 [2]
        Jmp ~X, Do_Zero Side 1 [1]
        Jmp Bitloop Side 1 [4]
    Do_Zero:
        Nop Side 0 [4]
    .Wrap
End Ws2812

Block Main
Declares
    Prog : Pio_Program
Implements
    Prog = Ws2812_Program()
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "ws2812.loom"
            obj = Path(tmp) / "ws2812.o"
            p.write_text(ws2812_src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"WS2812 PIO DSL compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

            nm = subprocess.run(["arm-none-eabi-nm", str(obj)], capture_output=True, text=True)
            self.assertEqual(nm.returncode, 0)
            self.assertIn("Ws2812_Instructions", nm.stdout)
            self.assertIn("Ws2812_Program", nm.stdout)
            self.assertIn("Ws2812_Load", nm.stdout)

    def test_dma_ownership_and_transfer(self):
        # 1. Accessing buffer while DMA is active must be rejected at compile time
        invalid_dma_src = r"""Module DmaSafetyTest
Block Main
Declares
    Tx_Buf : Unsigned_8 Array[64]
Implements
    Tx_Buf[1] = 0xAA
    Unsafe
        Dma.Transmit(0, Address(Tx_Buf[1]) as Unsigned_32, 64, Dma.Dreq.DREQ_FORCE)
    End Unsafe
    Tx_Buf[2] = 0xBB # ILLEGAL: Use-while-DMA-active
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "invalid_dma.loom"
            obj = Path(tmp) / "invalid_dma.o"
            p.write_text(invalid_dma_src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertNotEqual(res.returncode, 0, "Accessing buffer during active DMA transfer must fail compilation")
            self.assertIn("e3005", res.stderr.lower())
            self.assertIn("use-while-dma-active", res.stderr.lower())

        # 2. Accessing buffer after Dma.Wait_Complete must compile cleanly
        valid_dma_src = r"""Module DmaValidTest
Block Main
Declares
    Tx_Buf : Unsigned_8 Array[64]
Implements
    Tx_Buf[1] = 0xAA
    Unsafe
        Dma.Transmit(0, Address(Tx_Buf[1]) as Unsigned_32, 64, Dma.Dreq.DREQ_FORCE)
        Dma.Wait_Complete(0)
    End Unsafe
    Tx_Buf[1] = 0xCC # LEGAL: DMA has completed
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "valid_dma.loom"
            obj = Path(tmp) / "valid_dma.o"
            p.write_text(valid_dma_src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"Valid DMA transfer must compile cleanly:\n{res.stderr}")
            self.assertTrue(obj.is_file())

    def test_sio_interpolator_acceleration(self):
        interp_src = r"""Module InterpTest
Block Main
Declares
    Blended : Unsigned_32
    Interp_Val : Unsigned_32
    Lookup : Unsigned_32
Implements
    Blended = Interp.Blend(Interp.Unit.Unit_0, 100, 200, 128)
    Interp_Val = Interp.Linear_Interp(Interp.Unit.Unit_0, 0, 10, 100, 50, 50)
    Lookup = Interp.Table_Lookup(Interp.Unit.Unit_0, 0x20001000, 4, 2)
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "interp.loom"
            obj = Path(tmp) / "interp.o"
            p.write_text(interp_src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"SIO Interpolator compilation failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

    def test_static_stack_depth_analysis(self):
        # A task whose static stack limit is smaller than its WCSD must fail compilation
        overflow_src = r"""Module StackOverflowTest
Block Task_Deep
Declares
    Stack_Limit : Constant Unsigned_32 = 16
    Buffer : Unsigned_32 Array[32]
Implements
    Buffer[1] = 42
End Task_Deep

Block Main
Implements
    Task_Deep()
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "stack_ovf.loom"
            obj = Path(tmp) / "stack_ovf.o"
            p.write_text(overflow_src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertNotEqual(res.returncode, 0, "Stack overflow beyond Stack_Limit must be caught at compile time")
            self.assertIn("e4001", res.stderr.lower())
            self.assertIn("static stack overflow", res.stderr.lower())

    def test_block_periodic_realtime(self):
        periodic_src = r"""Module PeriodicTest
Block Sensor_Task Periodic 1000 Max_Jitter 10
Declares
    Val : Unsigned_32 = 0
Implements
    Val = Val + 1
End Sensor_Task

Block Main
Implements
    Spawn Sensor_Task()
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "periodic.loom"
            obj = Path(tmp) / "periodic.o"
            p.write_text(periodic_src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"Periodic task compilation failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

    def test_spinlock_dag_deadlock_elimination(self):
        # Circular lock order (Lock 1 then Lock 2, followed by Lock 2 then Lock 1) must be rejected
        deadlock_src = r"""Module DeadlockTest
Block Task_A
Implements
    Sync.Spinlock_Claim(1)
    Sync.Spinlock_Claim(2)
    Sync.Spinlock_Release(2)
    Sync.Spinlock_Release(1)
End Task_A

Block Task_B
Implements
    Sync.Spinlock_Claim(2)
    Sync.Spinlock_Claim(1) # CIRCULAR: Lock 1 was previously acquired before Lock 2
    Sync.Spinlock_Release(1)
    Sync.Spinlock_Release(2)
End Task_B

Block Main
Implements
    Task_A()
    Task_B()
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "deadlock.loom"
            obj = Path(tmp) / "deadlock.o"
            p.write_text(deadlock_src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertNotEqual(res.returncode, 0, "Circular spinlock acquisition must fail compilation")
            self.assertIn("e2005", res.stderr.lower())
            self.assertIn("circular lock order", res.stderr.lower())

    def test_mpu_and_crash_blackbox(self):
        blackbox_src = r"""Module BlackboxTest
Block Main
Declares
    Crashed : Boolean
    PC : Unsigned_32
Implements
    Watchdog.Enable(500, False)
    Watchdog.Feed()
    Crashed = Crash.Did_Crash()
    PC = Crash.Get_Last_PC()
    Crash.Print_Crash_Report()
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "blackbox.loom"
            obj = Path(tmp) / "blackbox.o"
            p.write_text(blackbox_src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"Watchdog and Crash Blackbox compilation failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

    def test_workspace_local_library_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "PicoApp"
            res_new = subprocess.run(["loom", "new", "PicoApp"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(res_new.returncode, 0, res_new.stderr)

            res_inst = subprocess.run(["loom", "install", "http-server"], cwd=str(ws), capture_output=True, text=True)
            self.assertEqual(res_inst.returncode, 0, f"loom install failed:\n{res_inst.stdout}\n{res_inst.stderr}")
            self.assertTrue((ws / ".loom" / "libraries" / "http-server").is_dir())
            self.assertIn("http-server", res_inst.stdout)

    def test_multi_module_dot_notation_init(self):
        src = r"""Module Main
Import RP2040
Import System
Import Clock
Import Time
Import Gpio
Import Uart
Import Spi
Import I2c
Import Pwm
Import Adc
Import Dma
Import Pio
Import Watchdog
Import Rtc
Import Multicore
Import Usb_Cdc

Block Main
Declares
    Rc : Signed_32 or Gpio_Error
    U : Uart.Uart_Device or Uart_Error
    S : Spi.Spi_Device or Spi_Error
    I : I2c.I2c_Device or I2c_Error
    P : Signed_32 or Pio_Error
    Chip : Unsigned_32
    Sys_Hz : Unsigned_32
Implements
    Chip = System.Chip_ID()
    Sys_Hz = Clock.Get_Sys_Hz()
    Gpio.Init_Output(Gpio.PICO_LED_PIN)
    Gpio.Write(Gpio.PICO_LED_PIN, True)
    U = Uart.Init(Uart.Uart_Port.UART0, 0, 1, 115200)
    S = Spi.Init(Spi.Spi_Port.SPI0, 16, 17, 18, 19, 1000000)
    I = I2c.Init(I2c.I2c_Port.I2C0, 4, 5, 100000)
    Pwm.Init()
    Adc.Init()
    Dma.Init()
    P = Pio.Init(0)
    Rtc.Init()
    Print("All modules initialized: <Chip:x> <Sys_Hz>\n")
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "multi.loom"
            obj = Path(tmp) / "multi.o"
            p.write_text(src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"Multi-module dot-notation compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

    def test_unsafe_gating(self):
        bad_cases = [
            ("vol_read", "Module T\nBlock Main Declares\n V : Unsigned_32\nImplements\n V = Vol_Read_32(0x40000000)\nEnd Main\n"),
            ("raw_addr", "Module T\nBlock Main Declares\n X : Signed_32 = 1\n P : Signed_32 Pointer\nImplements\n P = Address(X)\nEnd Main\n"),
            ("raw_deref", "Module T\nBlock Main Declares\n X : Signed_32 = 1\n P : Signed_32 Pointer\nImplements\n Unsafe\n P = Address(X)\n End Unsafe\n X = Deref(P)\nEnd Main\n"),
            ("mut_global", "Module T\nBlock Global Declares\n G : Unsigned_32 = 0\nEnd Global\nBlock Main Implements\n G = 1\nEnd Main\n"),
        ]
        good = """Module T
Block Global
    Declares
        G : Unsigned_32 = 0
End Global
Block Main
Declares
    X : Signed_32 = 1
    P : Signed_32 Pointer
    V : Unsigned_32
Implements
    Unsafe
        G = 42
        P = Address(X)
        X = Deref(P)
        V = Vol_Read_32(0x40000000)
    End Unsafe
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            for name, src in bad_cases:
                p = Path(tmp) / f"{name}.loom"
                p.write_text(src)
                res = subprocess.run([str(LOOMC_RP2040), "--check", str(p), "--baremetal"], capture_output=True, text=True)
                self.assertNotEqual(res.returncode, 0, f"{name} should require Unsafe on baremetal")
            gp = Path(tmp) / "good.loom"
            gp.write_text(good)
            res = subprocess.run([str(LOOMC_RP2040), "--check", str(gp), "--baremetal"], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Valid Unsafe block failed:\n{res.stderr}")

    def test_exhaustive_enum_match(self):
        bad = """Module T
Enum Color : Signed_32
    Red = 1
    Green = 2
    Blue = 3
End Color
Block Main
Declares
    C : Color = Color.Red
    X : Signed_32 = 0
Implements
    Match C
        When Color.Red:
            X = 1
        When Color.Green:
            X = 2
    End Match
End Main
"""
        good = """Module T
Enum Color : Signed_32
    Red = 1
    Green = 2
    Blue = 3
End Color
Block Main
Declares
    C : Color = Color.Red
    X : Signed_32 = 0
Implements
    Match C
        When Color.Red:
            X = 1
        When Color.Green:
            X = 2
        When Color.Blue:
            X = 3
    End Match
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "bad_match.loom"
            bp.write_text(bad)
            res_bad = subprocess.run([str(LOOMC_RP2040), "--check", str(bp)], capture_output=True, text=True)
            self.assertNotEqual(res_bad.returncode, 0, "Non-exhaustive enum Match should fail")
            self.assertIn("Blue", res_bad.stderr)

            gp = Path(tmp) / "good_match.loom"
            gp.write_text(good)
            res_good = subprocess.run([str(LOOMC_RP2040), "--check", str(gp)], capture_output=True, text=True)
            self.assertEqual(res_good.returncode, 0, f"Exhaustive enum Match failed:\n{res_good.stderr}")

    def test_ignored_error_return_rejected(self):
        bad = """Module T
Import Uart
Block Main
Implements
    Uart.Init(Uart.Uart_Port.UART0, 0, 1, 115200)
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "ignored_err.loom"
            p.write_text(bad)
            res = subprocess.run([str(LOOMC_RP2040), "--check", str(p), "-I", str(BSP_DIR)], capture_output=True, text=True)
            self.assertIn("warning", res.stderr.lower(), "Ignoring Error return should emit a warning")

    def test_baremetal_recursion_rejected(self):
        direct = """Module T
Block Rec Takes N : Unsigned_32 Produces Unsigned_32
Implements
    If N == 0
        Give 0
    End If
    Give Rec(N - 1)
End Rec
Block Main
Declares
    V : Unsigned_32
Implements
    V = Rec(3)
End Main
"""
        mutual = """Module T
Block B Takes N : Unsigned_32 Produces Unsigned_32
Implements
    If N == 0
        Give 0
    End If
    Give A(N - 1)
End B
Block A Takes N : Unsigned_32 Produces Unsigned_32
Implements
    Give B(N)
End A
Block Main
Declares
    V : Unsigned_32
Implements
    V = A(3)
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            for name, src in [("direct", direct), ("mutual", mutual)]:
                p = Path(tmp) / f"{name}.loom"
                p.write_text(src)
                res = subprocess.run([str(LOOMC_RP2040), "--check", str(p), "--baremetal"], capture_output=True, text=True)
                self.assertNotEqual(res.returncode, 0, f"{name} recursion should fail on baremetal")

    def test_pin_conflict_and_irq_spinlock_compile(self):
        src = """Module Main
Import RP2040
Import System
Import Gpio
Import Adc
Import Multicore

Block Main
Declares
    Pin25 : Constant Gpio.Pin = 25
    Pin26 : Constant Gpio.Pin = 26
    Arc : Signed_32 or Adc_Error
    Saved : Unsigned_32
Implements
    Saved = System.Save_And_Disable_IRQ()
    Multicore.Spinlock_Lock(0)
    Gpio.Init_Output(Pin25)
    Pin25.High
    Gpio.Deinit(Pin25)
    Arc = Adc.Init_Pin(Pin26)
    Multicore.Spinlock_Unlock(0)
    System.Restore_IRQ(Saved)
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "safety.loom"
            obj = Path(tmp) / "safety.o"
            p.write_text(src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"Safety API compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

    def test_ada_style_dotted_modules_generics_and_tagged_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "glyph.display.ssd1306.mono.loom").write_text("""Module Glyph.Display.SSD1306.Mono
Enum Color : Unsigned_8
    Black = 0
    White = 1
End Color
Block Global
    Declares
        WIDTH : Constant Unsigned_32 = 128
End Global
Block Get_Width Produces Unsigned_32
Implements
    Give WIDTH
End Get_Width
""")
            (ws / "glyph.display.loom").write_text("""Generic Module Glyph.Display[P] Takes W : Unsigned_32, H : Unsigned_32
Block Get_Area Produces Unsigned_32
Implements
    Give W * H
End Get_Area
End Display
""")
            main_p = ws / "main.loom"
            main_p.write_text(r"""Module Main
Import Glyph.Display.SSD1306.Mono As OLED
Import Glyph.Display.PanelA = Glyph.Display[Unsigned_8](128, 64)
Import Glyph.Display.PanelB = Glyph.Display[Unsigned_16](132, 32)

Tagged Record Shape
    X : Signed_32
End Shape

Block Area Takes Self : Shape Pointer Produces Signed_32
Implements
    Give 0
End Area

Record Rect Inherits Shape
    W : Signed_32
    H : Signed_32
End Rect

Block Area Takes Self : Rect Pointer Produces Signed_32
Implements
    Give Self.W * Self.H
End Area

Block Main
Declares
    W : Unsigned_32
    A1 : Unsigned_32
    A2 : Unsigned_32
    C : Color
    R : Rect = Rect{ X: 1, W: 6, H: 7 }
    S : Shape Pointer
    Total : Signed_32
Implements
    W = OLED.Get_Width
    C = Glyph.Display.SSD1306.Mono.Color.White
    A1 = Glyph.Display.PanelA.Get_Area
    A2 = Glyph.Display.PanelB.Get_Area
    Unsafe
        S = Address(R)
        Total = R.Area() + S.Area()
    End Unsafe
    Print("<W> <C> <A1> <A2> <Total>\n")
End Main
""")
            obj = ws / "ada.o"
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(main_p), str(obj), "--baremetal", "-I", str(ws)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"Ada-style RP2040 compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

    def test_dual_stack_psp_and_spawn_privileged(self):
        # Baremetal dual-stack privilege separation: Spawn Task (unprivileged) vs Spawn Privileged Task
        src = r"""Module DualStackTest
Import Thread
Import Sync

Block Privileged_Driver
Implements
    Loop
        Thread.Yield()
    End Loop
End Privileged_Driver

Block User_Worker
Implements
    Loop
        Thread.Yield()
    End Loop
End User_Worker

Block Main
Implements
    # Unprivileged Thread-mode task on PSP
    Spawn User_Worker()
    # Privileged Thread-mode task on PSP for system drivers
    Spawn Privileged Privileged_Driver()
    Spawn Privileged Task Privileged_Driver()
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "dual_stack.loom"
            obj = Path(tmp) / "dual_stack.o"
            p.write_text(src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"Dual stack compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

    def test_sram_vtor_zero_jitter_interrupt(self):
        # Verify that VTOR is relocated to SRAM Scratchpad Bank 4 (0x20040000)
        c_file = PICO_ROOT / "sdk" / "targets" / "rp2040" / "usb_cdc_rt.c"
        content = c_file.read_text()
        self.assertIn("0x20040000u", content)
        self.assertIn("relocate_vtor_to_sram", content)
        # Verify Core 1 launch vector table uses 0x20040000
        sched_file = PICO_ROOT / "sdk" / "targets" / "rp2040" / "scheduler_kernel.c"
        sched_content = sched_file.read_text()
        self.assertIn("0x20040000", sched_content)

    def test_pio_sm_advanced_config_and_irq(self):
        # Verify PIO FIFO joining, shift control, pin mapping and Pio_Interrupt handler syntax
        src = r"""Module PioAdvancedTest
Import Pio
Import RP2040

Pio_Program Square_Wave
Implements
    .Wrap_Target
    Set Pins, 1   [1]
    Set Pins, 0   [1]
    .Wrap
End Square_Wave

Block Pio_Handler Pio_Interrupt(0, 0)
Implements
    Pio.IRQ_Clear(0, 0, 1)
End Pio_Handler

Block Main
Declares
    Prog : Pio.Pio_Program
Implements
    Pio.Init(0)
    Prog = Square_Wave_Program()
    Pio.SM_Init_Default(0, 0, Prog, 16, 1)
    Pio.SM_Set_FIFO_Join(0, 0, Pio.FIFO_Join.Join_TX)
    Pio.SM_Set_Shift(0, 0, True, False, 32, 32, False, True)
    Pio.SM_Set_Pin_Mappings(0, 0, 16, 1, 16, 1, 16, 0, 0)
    Pio.IRQ_Set_Enabled(0, 0, 1, True)
    Pio.SM_Set_Enabled(0, 0, True)
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "pio_adv.loom"
            obj = Path(tmp) / "pio_adv.o"
            p.write_text(src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"PIO advanced compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

    def test_sio_hardware_divider_and_fifos(self):
        # Verify SIO Hardware Divider (/ and %) and cross-core hardware FIFOs
        src = r"""Module SioTest
Import Sio

Block Main
Declares
    A : Unsigned_32 = 1000000
    B : Unsigned_32 = 7
    Q : Unsigned_32
    R : Unsigned_32
    SA : Signed_32 = -5000
    SB : Signed_32 = 12
    SQ : Signed_32
    SR : Signed_32
    Async_Q : Unsigned_32
    Has_Data : Boolean
Implements
    # Compiler automatic SIO Hardware Divider replacement
    Q = A / B
    R = A % B
    SQ = SA / SB
    SR = SA % SB

    # Explicit asynchronous non-blocking Sio API
    Sio.Div_Start_Unsigned(A, B)
    # Hardware performs 8-cycle pipelined division while CPU does other work
    Has_Data = Sio.FIFO_Has_Data()
    Async_Q = Sio.Div_Result()

    # Cross-Core SIO Hardware FIFOs
    If Sio.FIFO_Is_Ready()
        Sio.FIFO_Push(42)
    End If
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sio_test.loom"
            obj = Path(tmp) / "sio_test.o"
            ll = Path(tmp) / "sio_test.ll"
            p.write_text(src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"SIO test compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())

            # Also check LLVM IR output to verify hardware divider registers (0xD0000060, 0xD0000070)
            res_ll = subprocess.run(
                [str(LOOMC_RP2040), str(p), str(ll), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res_ll.returncode, 0, f"SIO IR generation failed:\n{res_ll.stderr}")
            ll_content = ll.read_text()
            self.assertIn("sio_udiv_res", ll_content)
            self.assertIn("sio_sdiv_res", ll_content)

    def test_system_sleep_on_exit(self):
        # Verify System module Cortex-M0+ SCR.SLEEPONEXIT and deep sleep
        src = r"""Module SleepTest
Import System

Block Main
Declares
    Is_Sleep : Boolean
Implements
    System.Set_Sleep_On_Exit(True)
    Is_Sleep = System.Get_Sleep_On_Exit()
    System.Set_Sleep_Deep(False)
    System.Set_Sleep_On_Exit(False)
End Main
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sleep_test.loom"
            obj = Path(tmp) / "sleep_test.o"
            p.write_text(src)
            res = subprocess.run(
                [str(LOOMC_RP2040), "--object", str(p), str(obj), "--baremetal", "-I", str(BSP_DIR), "-I", str(STD_DIR)],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"Sleep-on-exit compile failed:\n{res.stderr}")
            self.assertTrue(obj.is_file())


if __name__ == "__main__":
    unittest.main()
