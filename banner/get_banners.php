<?php
/**
 * ==========================================================================
 * Shree Chautara Secondary School - Server-side Banner Auto-Detector
 * Website: www.chautaramavi.edu.np
 * 
 * Automatically scans the 'banner/banner_img/' folder and returns
 * a JSON array of supported media files.
 * ==========================================================================
 */

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-cache, must-revalidate');

$targetDir = __DIR__ . '/banner_img';
$relativePath = 'banner/banner_img/';

// Supported extensions
$allowedExtensions = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'pdf', 'mp4', 'webm', 'ogg'];
$mediaFiles = [];

if (is_dir($targetDir)) {
    $scannedFiles = scandir($targetDir);
    if ($scannedFiles !== false) {
        $temp = [];
        foreach ($scannedFiles as $file) {
            if ($file === '.' || $file === '..') {
                continue;
            }
            $ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
            if (in_array($ext, $allowedExtensions)) {
                $priority = in_array($ext, ['jpg', 'jpeg', 'png', 'webp', 'gif']) ? 0 : ($ext === 'pdf' ? 1 : 2);
                $temp[] = [
                    'priority' => $priority,
                    'name' => $file,
                    'path' => $relativePath . $file
                ];
            }
        }
        usort($temp, function ($a, $b) {
            if ($a['priority'] === $b['priority']) {
                return strnatcasecmp($a['name'], $b['name']);
            }
            return $a['priority'] <=> $b['priority'];
        });
        foreach ($temp as $item) {
            $mediaFiles[] = $item['path'];
        }
    }
}

echo json_encode(array_values($mediaFiles), JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
exit;
