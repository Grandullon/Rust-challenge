#Requires -Version 5.1
<#
  Dashboard de Tareas Periódicas · HUVN · RRHH
  --------------------------------------------
  Este script recorre las carpetas de red configuradas, comprueba qué
  archivos existen para cada periodo (mes / día) y genera un
  dashboard.html estático junto a sí mismo. El HTML se abre solo al
  final.

  Uso:  doble clic en actualizar-dashboard.bat
        (o ejecutar este .ps1 directamente desde PowerShell)

  Para añadir o cambiar tareas, edita el bloque $tareas más abajo.
#>

$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# =====================================================================
#                          CONFIGURACIÓN
# =====================================================================
# Tokens admitidos en Ruta y Patron: {YYYY}, {MM}, {DD}, {MES_TEXTO}
$tareas = @(
    [PSCustomObject]@{
        Id              = 'continuidad_asistencial'
        Nombre          = 'Continuidad Asistencial'
        Area            = 'Dirección Médica'
        Ruta            = '\\Alhambra\grupo$\GrupodeApoyoGestion\H. VIRGEN NIEVES 2026\SEGUIMIENTO JC_CA\CONTINUIDAD ASISTENCIAL\C.A. X MESES'
        Periodicidad    = 'mensual'
        Patron          = '{MM}-{YYYY}-CA'
        Extension       = 'xlsx'
        SubcarpetaPorMes= $false
        DiasLaborables  = $false
    },
    [PSCustomObject]@{
        Id              = 'personal_activo'
        Nombre          = 'Personal Activo'
        Area            = 'RRHH'
        Ruta            = '\\Alhambra\grupo$\HUVN-PERSONAL-ACTIVO\Personal Activo\{YYYY}'
        Periodicidad    = 'diaria'
        Patron          = 'PA-{YYYY}-{MM}-{DD}'
        Extension       = 'xlsx'
        SubcarpetaPorMes= $false
        DiasLaborables  = $true
    },
    [PSCustomObject]@{
        Id              = 'it_diaria'
        Nombre          = 'IT Diaria'
        Area            = 'RRHH'
        Ruta            = '\\Alhambra\grupo$\HUVN-PERSONAL-ACTIVO\IT DIARIA\IT DIARIA\{YYYY}'
        Periodicidad    = 'diaria'
        Patron          = 'IT-HVN-{YYYY}-{MM}-{DD}'
        Extension       = 'xlsx'
        SubcarpetaPorMes= $true
        DiasLaborables  = $true
    },
    [PSCustomObject]@{
        Id              = 'altas_it'
        Nombre          = 'Altas IT'
        Area            = 'RRHH'
        Ruta            = '\\Alhambra\grupo$\HUVN-PERSONAL-ACTIVO\IT DIARIA\ALTAS IT\{YYYY}'
        Periodicidad    = 'diaria'
        Patron          = 'ALTAS IT A {YYYY}-{MM}-{DD}'
        Extension       = 'xlsx'
        SubcarpetaPorMes= $true
        DiasLaborables  = $true
    }
)

# =====================================================================
#                              MOTOR
# =====================================================================
$ahora     = Get-Date
$anio      = $ahora.Year
$mesActual = $ahora.Month
$diaActual = $ahora.Day
$meses     = @('enero','febrero','marzo','abril','mayo','junio',
               'julio','agosto','septiembre','octubre','noviembre','diciembre')

function Resolver-Ruta {
    param([string]$ruta, [int]$anio, [int]$mes)
    $r = $ruta.Replace('{YYYY}', "$anio").Replace('{MM}', ('{0:D2}' -f $mes))
    if ($mes -ge 1 -and $mes -le 12) {
        $r = $r.Replace('{MES_TEXTO}', $meses[$mes-1])
    }
    return $r
}

function Resolver-Patron {
    param([string]$patron, [int]$anio, [int]$mes, [int]$dia = 0)
    $p = $patron.Replace('{YYYY}', "$anio").Replace('{MM}', ('{0:D2}' -f $mes))
    $p = $p.Replace('{MES_TEXTO}', $meses[$mes-1])
    if ($dia -gt 0) { $p = $p.Replace('{DD}', ('{0:D2}' -f $dia)) }
    return $p
}

function Buscar-SubcarpetaMes {
    param([string]$rutaBase, [int]$mes)
    if (-not (Test-Path -LiteralPath $rutaBase)) { return $null }
    $nombreMes  = $meses[$mes-1]
    $mmStr      = '{0:D2}' -f $mes
    $candidatas = Get-ChildItem -LiteralPath $rutaBase -Directory -ErrorAction SilentlyContinue
    foreach ($c in $candidatas) {
        $lower = $c.Name.ToLower()
        if ($lower -eq $nombreMes -or $lower.Contains($nombreMes) -or
            $lower -eq $mmStr -or $lower.StartsWith("$mmStr-") -or $lower.StartsWith("$mmStr ")) {
            return $c.FullName
        }
    }
    return $null
}

function Comprobar-Mensual {
    param($tarea)
    $resultado = [ordered]@{
        id            = $tarea.Id
        nombre        = $tarea.Nombre
        area          = $tarea.Area
        periodicidad  = 'mensual'
        ruta          = $tarea.Ruta
        rutaResuelta  = ''
        carpetaExiste = $false
        error         = $null
        meses         = [ordered]@{}
    }
    $rutaCarpeta = Resolver-Ruta $tarea.Ruta $anio 1
    $resultado.rutaResuelta = $rutaCarpeta
    if (-not (Test-Path -LiteralPath $rutaCarpeta)) {
        $resultado.error = "No se localiza la carpeta"
        for ($m = 1; $m -le 12; $m++) {
            $resultado.meses["$m"] = @{ estado = 'sin-carpeta' }
        }
        return $resultado
    }
    $resultado.carpetaExiste = $true
    $archivos = Get-ChildItem -LiteralPath $rutaCarpeta -File -Filter "*.$($tarea.Extension)" -ErrorAction SilentlyContinue

    for ($m = 1; $m -le 12; $m++) {
        $patronM = Resolver-Patron $tarea.Patron $anio $m
        $regex   = [regex]::Escape($patronM)
        $match   = $archivos | Where-Object { $_.Name -imatch $regex } | Select-Object -First 1
        if ($match) {
            $resultado.meses["$m"] = @{
                estado = 'verde'; archivo = $match.Name; ruta = $match.FullName
            }
        } elseif ($m -gt $mesActual) {
            $resultado.meses["$m"] = @{ estado = 'gris' }
        } elseif ($m -eq $mesActual) {
            $resultado.meses["$m"] = @{ estado = 'amber' }
        } else {
            $resultado.meses["$m"] = @{ estado = 'rojo' }
        }
    }
    return $resultado
}

function Comprobar-Diaria {
    param($tarea)
    $resultado = [ordered]@{
        id             = $tarea.Id
        nombre         = $tarea.Nombre
        area           = $tarea.Area
        periodicidad   = 'diaria'
        ruta           = $tarea.Ruta
        diasLaborables = [bool]$tarea.DiasLaborables
        rutaResuelta   = ''
        carpetaExiste  = $false
        error          = $null
        dias           = [ordered]@{}
    }
    $rutaBase = Resolver-Ruta $tarea.Ruta $anio $mesActual
    $resultado.rutaResuelta = $rutaBase
    if (-not (Test-Path -LiteralPath $rutaBase)) {
        $resultado.error = "No se localiza la carpeta"
        return $resultado
    }
    $resultado.carpetaExiste = $true

    $mesesAExplorar = @($mesActual)
    if ($mesActual -gt 1) { $mesesAExplorar = @(($mesActual - 1), $mesActual) }

    foreach ($mes in $mesesAExplorar) {
        $carpetaMes = $rutaBase
        if ($tarea.SubcarpetaPorMes) {
            $carpetaMes = Buscar-SubcarpetaMes $rutaBase $mes
            if (-not $carpetaMes) { continue }
        }
        $archivos = Get-ChildItem -LiteralPath $carpetaMes -File -Filter "*.$($tarea.Extension)" -ErrorAction SilentlyContinue
        $diasEnMes = [DateTime]::DaysInMonth($anio, $mes)
        for ($d = 1; $d -le $diasEnMes; $d++) {
            $patronD = Resolver-Patron $tarea.Patron $anio $mes $d
            $regex   = [regex]::Escape($patronD)
            $match   = $archivos | Where-Object { $_.Name -imatch $regex } | Select-Object -First 1
            $clave   = "$mes-$d"
            $fecha   = Get-Date -Year $anio -Month $mes -Day $d
            $finSemana = ($fecha.DayOfWeek -eq 'Saturday' -or $fecha.DayOfWeek -eq 'Sunday')
            $futuro    = ($mes -gt $mesActual) -or ($mes -eq $mesActual -and $d -gt $diaActual)

            if ($match) {
                $resultado.dias[$clave] = @{
                    estado = 'verde'; archivo = $match.Name; ruta = $match.FullName
                    finSemana = $finSemana; mes = $mes; dia = $d
                }
            } elseif ($futuro) {
                $resultado.dias[$clave] = @{ estado = 'gris'; finSemana = $finSemana; mes = $mes; dia = $d }
            } elseif ($tarea.DiasLaborables -and $finSemana) {
                $resultado.dias[$clave] = @{ estado = 'gris'; finSemana = $finSemana; mes = $mes; dia = $d }
            } elseif ($mes -eq $mesActual -and $d -eq $diaActual) {
                $resultado.dias[$clave] = @{ estado = 'amber'; finSemana = $finSemana; mes = $mes; dia = $d }
            } else {
                $resultado.dias[$clave] = @{ estado = 'rojo'; finSemana = $finSemana; mes = $mes; dia = $d }
            }
        }
    }
    return $resultado
}

# =====================================================================
#                       EJECUTAR COMPROBACIONES
# =====================================================================
Write-Host ""
Write-Host "Dashboard de Tareas Periodicas - HUVN - RRHH" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
$datos = @()
foreach ($t in $tareas) {
    Write-Host ("  - {0,-30} " -f $t.Nombre) -NoNewline
    try {
        $r = $null
        switch ($t.Periodicidad) {
            'mensual' { $r = Comprobar-Mensual $t }
            'diaria'  { $r = Comprobar-Diaria  $t }
            default   {
                Write-Host "(periodicidad no soportada)" -ForegroundColor Yellow
                continue
            }
        }
        if ($r.error) {
            Write-Host "[!] $($r.error)" -ForegroundColor Yellow
        } elseif ($r.periodicidad -eq 'mensual') {
            $hechos = ($r.meses.Values | Where-Object { $_.estado -eq 'verde' }).Count
            Write-Host "[OK] $hechos / 12 meses" -ForegroundColor Green
        } else {
            $hechos = ($r.dias.Values | Where-Object { $_.estado -eq 'verde' }).Count
            Write-Host "[OK] $hechos archivos" -ForegroundColor Green
        }
        $datos += $r
    } catch {
        Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
        $datos += [ordered]@{
            id = $t.Id; nombre = $t.Nombre; area = $t.Area
            periodicidad = $t.Periodicidad; ruta = $t.Ruta
            error = $_.Exception.Message; meses = @{}; dias = @{}
        }
    }
}

# =====================================================================
#                       GENERAR HTML
# =====================================================================
$rutaPlantilla = Join-Path $PSScriptRoot 'plantilla.html'
if (-not (Test-Path -LiteralPath $rutaPlantilla)) {
    Write-Host ""
    Write-Host "ERROR: no se encuentra plantilla.html junto al script." -ForegroundColor Red
    Write-Host "Asegurate de tener los 3 archivos en la misma carpeta:" -ForegroundColor Red
    Write-Host "  - actualizar-dashboard.bat" -ForegroundColor Red
    Write-Host "  - actualizar-dashboard.ps1" -ForegroundColor Red
    Write-Host "  - plantilla.html" -ForegroundColor Red
    Read-Host "Pulsa Enter para salir"
    exit 1
}

$plantilla   = Get-Content -LiteralPath $rutaPlantilla -Raw -Encoding UTF8
$datosJson   = ($datos  | ConvertTo-Json -Depth 10 -Compress)
$fechaTexto  = $ahora.ToString("dd/MM/yyyy HH:mm")
$mesTextoMay = $meses[$mesActual-1].ToUpper()

# Reemplazo literal (no regex) — evita que $1, grupo$ etc. se interpreten
$html = $plantilla
$html = $html.Replace('__DATOS_JSON__', $datosJson)
$html = $html.Replace('__FECHA_ACTUALIZACION__', $fechaTexto)
$html = $html.Replace('__ANIO__', "$anio")
$html = $html.Replace('__MES_TEXTO__', $mesTextoMay)
$html = $html.Replace('__MES_NUMERO__', "$mesActual")
$html = $html.Replace('__DIA__', "$diaActual")

$rutaSalida = Join-Path $PSScriptRoot 'dashboard.html'
[System.IO.File]::WriteAllText($rutaSalida, $html, [System.Text.UTF8Encoding]::new($false))

Write-Host ""
Write-Host "Dashboard generado:" -ForegroundColor Green
Write-Host "  $rutaSalida" -ForegroundColor Green
Write-Host ""
Write-Host "Abriendo en el navegador..."
Start-Process $rutaSalida
