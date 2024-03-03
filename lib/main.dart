import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:ffmpeg_kit_flutter/ffmpeg_kit.dart';
import 'package:gallery_saver/gallery_saver.dart';
import 'package:permission_handler/permission_handler.dart';
import 'dart:io';

void main() => runApp(MyApp());

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Video to Images App',
      theme: ThemeData(
        primarySwatch: Colors.blue,
      ),
      home: MyHomePage(),
    );
  }
}

class MyHomePage extends StatefulWidget {
  @override
  _MyHomePageState createState() => _MyHomePageState();
}

Future<void> _requestPermission() async {
  PermissionStatus status = await Permission.manageExternalStorage.status;

  if (!status.isGranted) {
    status = await Permission.manageExternalStorage.request();
  }
}

class _MyHomePageState extends State<MyHomePage> {
  String _videoPath = '';
  String _customPath = '';
  int _intervalSeconds = 10;

  Future<void> _pickVideo() async {
    // Request permission to save images and wait for the user's response
    await _requestPermission();

    PermissionStatus status = await Permission.manageExternalStorage.status;

    if (status.isGranted) {
      FilePickerResult? result =
          await FilePicker.platform.pickFiles(type: FileType.video);

      if (result != null) {
        setState(() {
          _videoPath = result.files.single.path!;
        });
        _extractImagesFromVideo();
      }
    } else {
      // エラーログの表示
      if (kDebugMode) {
        print('Permission denied');
      }
    }
  }

  Future<void> _extractImagesFromVideo() async {
    final imagePath = '$_customPath/image_%03d.jpg';

    await FFmpegKit.execute('-i $_videoPath -vf "fps=1/$_intervalSeconds" $imagePath').then((session) async {
      final returnCode = await session.getReturnCode();
      if (returnCode!.isValueSuccess()) {
        for (int i = 0; i < 10; i++) {
          final imageFile = File('$_customPath/image_${i.toString().padLeft(3, '0')}.jpg');
          if (imageFile.existsSync()) {
            await GallerySaver.saveImage(imageFile.path);
          }
        }
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Video to Images App'),
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            TextField(
              decoration: InputDecoration(hintText: 'Enter custom path for saving images'),
              onChanged: (value) {
                _customPath = value;
              },
            ),
            TextField(
              decoration: InputDecoration(hintText: 'Enter interval in seconds (default 10)'),
              keyboardType: TextInputType.number,
              onChanged: (value) {
                _intervalSeconds = int.tryParse(value) ?? 10;
              },
            ),
            ElevatedButton(
              onPressed: _pickVideo,
              child: Text('Pick a Video'),
            ),
            Text(_videoPath),
          ],
        ),
      ),
    );
  }
}
