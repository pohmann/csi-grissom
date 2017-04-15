int main(int argc, char** argv){
  if(argc < 3)
    argc++;
  else
    argc += 4;
  printf("%d\n", argc);
}
