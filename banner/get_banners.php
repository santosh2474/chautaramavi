<?php
/**
 * ==========================================================================
 * Shree Chautara Secondary School - Server-side Banner Auto-Detector
 * Website: www.chautaramavi.edu.np
 * 
 * Automatically scans the 'banner/banner_img/' folder, synchronizes with
 * 'banner_meta.json', and returns media paths and metadata with anti-cache headers.
 * ==========================================================================
 */

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');
header('Expires: 0');

$targetDir = __DIR__ . '/banner_img';
$metaFile = __DIR__ . '/banner_meta.json';
$relativePath = 'banner/banner_img/';

// Load banner_meta.json if present
$metaData = [];
$metaMtime = 0;
if (file_exists($metaFile)) {
    $metaMtime = filemtime($metaFile);
    $metaContent = @file_get_contents($metaFile);
    if ($metaContent) {
        $decoded = json_decode($metaContent, true);
        if (is_array($decoded)) {
            $metaData = $decoded;
        }
    }
}

// Supported extensions
$allowedExtensions = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'pdf', 'mp4', 'webm', 'ogg'];
$mediaFiles = [];
$itemDetails = [];
$hashParts = [];

if (is_dir($targetDir)) {
    $scannedFiles = scandir($targetDir);
    if ($scannedFiles !== false) {
        $temp = [];
        foreach ($scannedFiles as $file) {
            if ($file === '.' || $file === '..') {
                continue;
            }
            $fullPath = $targetDir . '/' . $file;
            $ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
            if (in_array($ext, $allowedExtensions) && is_file($fullPath)) {
                $priority = in_array($ext, ['jpg', 'jpeg', 'png', 'webp', 'gif']) ? 0 : ($ext === 'pdf' ? 1 : 2);
                $mtime = filemtime($fullPath);
                $relPath = $relativePath . $file;
                $title = isset($metaData[$relPath]['title']) ? $metaData[$relPath]['title'] : '';

                $temp[] = [
                    'priority' => $priority,
                    'name' => $file,
                    'path' => $relPath,
                    'mtime' => $mtime,
                    'title' => $title
                ];
                $hashParts[] = $relPath . ':' . $mtime . ':' . $title;
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
            $itemDetails[] = [
                'url' => $item['path'],
                'name' => $item['name'],
                'mtime' => $item['mtime'],
                'title' => $item['title']
            ];
        }
    }
}

$contentHash = md5(implode('|', $hashParts) . '|meta:' . $metaMtime);

$response = [
    'media' => array_values($mediaFiles),
    'meta' => $metaData,
    'items' => $itemDetails,
    'contentHash' => $contentHash,
    'lastModified' => time()
];

echo json_encode($response, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
exit;
