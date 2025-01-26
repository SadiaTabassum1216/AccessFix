import { Component } from '@angular/core';
import { AnalysisService } from '../../services/analysis.service';
import { Analysis } from 'src/app/models/analysis';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent {
  report: Analysis | null = null;
  title: string = 'AccessFix';
  code: string = '';
  url: string = '';
  fileContent: File | null = null;
  errorMessage: string = '';
  selectedFileName: string = 'Select a file';
  loading: boolean = false;

  showChat = false;
  messages: { text: string; sender: string }[] = [];
  userInput = '';

  constructor(private codeAnalysisService: AnalysisService, private http: HttpClient) {}

  handleSubmit(): void {
    this.errorMessage = '';
    this.loading = true;
    this.report = null;

    if (this.code) {
      this.codeAnalysisService.analyzeCode(this.code).subscribe(
        response => {
          this.report = response;
          this.clearFields();
          this.loading = false;
        },
        error => {
          this.errorMessage = 'Error analyzing code.';
          this.loading = false;
        }
      );
    } else if (this.url) {
      this.codeAnalysisService.analyzeUrl(this.url).subscribe(
        response => {
          this.report = response;
          this.clearFields();
          this.loading = false;
        },
        error => {
          this.errorMessage = 'Error analyzing URL.';
          this.loading = false;
        }
      );
    } else if (this.fileContent) {
      const file = this.fileContent;  // Directly use the file here, not FormData
    
      // Send file object to analyzeFile method
      this.codeAnalysisService.analyzeFile(file).subscribe(
        response => {
          this.report = response;
          this.clearFields();
          this.loading = false;
        },
        error => {
          this.errorMessage = 'Error analyzing file.';
          this.loading = false;
        }
      );
    }
    else {
      this.errorMessage = 'Please enter code, select a file, or enter a URL.';
      this.loading = false;
    }
  }

  handleFileChange(input: any): void {
    const file = input.files[0];
    if (file) {
      this.fileContent = file;
      this.code = ''; // Clear code if file is selected
      this.selectedFileName = file.name;
    } else {
      this.errorMessage = 'Please select a valid file.';
      this.selectedFileName = 'Select a file';
    }
  }

  toggleChat() {
    this.showChat = !this.showChat;
    if (!this.showChat) {
      this.messages = []; // Clean chat when closed
    }
  }

  sendMessage() {
    if (this.userInput.trim()) {
      this.messages.push({ text: this.userInput, sender: 'user' });
      this.http.post<any>('API_ENDPOINT', { message: this.userInput })
        .subscribe(response => {
          this.messages.push({ text: response, sender: 'bot' });
          this.userInput = ''; // Clear input after sending
        });
         
        // Simulate response from an API by directly adding the "Hello World" response
      //   setTimeout(() => {
      //     this.messages.push({ text: 'Hello World', sender: 'bot' });
      // }, 500); // Adding a timeout to simulate network delay
      
      this.userInput = '';
    }
  }

  clearFields(): void {
    this.code = '';
    this.url = '';
    this.fileContent = null;
    this.selectedFileName = 'Select a file';
  }
}
